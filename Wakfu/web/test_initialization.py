import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import server
from initialization import Initialization
from snapshot import fingerprint, verify
import update

class InitializationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        (self.root/'updater').mkdir()
        (self.root/'updater/reference.json').write_text(json.dumps({'manifest':{'version':'test'}}))
    def tearDown(self):
        self.tmp.cleanup()
    def test_no_overwrite_or_personal_reset(self):
        (self.root/'wakfu.sqlite').write_bytes(b'existing database')
        (self.root/'personal.sqlite').write_bytes(b'user data')
        job=Initialization(self.root)
        with self.assertRaises(ValueError):job.start()
        with self.assertRaises(ValueError):update.update(self.root,self.root/'updater/reference.json')
        self.assertEqual((self.root/'wakfu.sqlite').read_bytes(),b'existing database')
        self.assertEqual((self.root/'personal.sqlite').read_bytes(),b'user data')
        self.assertFalse((self.root/'.update.lock').exists())
    def test_verification_rejects_changed_content(self):
        path=self.root/'fixture.sqlite'
        with closing(sqlite3.connect(path)) as db, db:db.executescript('CREATE TABLE items(id INTEGER PRIMARY KEY,name TEXT);INSERT INTO items VALUES(1,"Bouftou");')
        reference=json.loads(json.dumps({'tables':fingerprint(path)}))
        verify(path,reference)
        with closing(sqlite3.connect(path)) as db, db:db.execute('UPDATE items SET name="changed"')
        with self.assertRaises(ValueError):verify(path,reference)
    def test_failed_build_never_publishes_database(self):
        reference={'manifest':{'version':'test'},'tables':{}}
        (self.root/'updater/reference.json').write_text(json.dumps(reference))
        with patch.object(update,'download',return_value={}),patch.object(update,'build',side_effect=ValueError('failed')):
            with self.assertRaises(ValueError):update.update(self.root,self.root/'updater/reference.json')
        self.assertFalse((self.root/'wakfu.sqlite').exists())
        self.assertFalse((self.root/'.update.lock').exists())
        self.assertEqual(list(self.root.glob('.wakfu-build-*')),[])
    def test_success_publishes_verified_database_and_preserves_personal(self):
        reference={'manifest':{'version':'test'},'tables':{}}
        (self.root/'updater/reference.json').write_text(json.dumps(reference))
        (self.root/'personal.sqlite').write_bytes(b'private preferences')
        def build(folder,destination):
            with closing(sqlite3.connect(destination)) as db, db:db.execute('CREATE TABLE metadata(key,value)')
            return {'version':'test','counts':{},'audit':{},'database_bytes':destination.stat().st_size}
        with patch.object(update,'download',return_value={}),patch.object(update,'build',side_effect=build):
            update.update(self.root,self.root/'updater/reference.json')
        self.assertTrue((self.root/'wakfu.sqlite').exists())
        self.assertEqual((self.root/'personal.sqlite').read_bytes(),b'private preferences')
        self.assertFalse((self.root/'.update.lock').exists())
    def test_missing_database_page_and_api(self):
        job=Initialization(self.root)
        with patch.object(server,'ROOT',self.root),patch.object(server,'PERSONAL',self.root/'personal.sqlite'),patch.object(server,'INITIALIZATION',job):
            server.initialize_personal()
            with closing(sqlite3.connect(self.root/'personal.sqlite')) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM item_preferences').fetchone()[0],0)
            http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
            thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
            base='http://127.0.0.1:'+str(http.server_port)
            try:
                with urllib.request.urlopen(base+'/') as response:
                    self.assertTrue(response.url.endswith('/initialisation'))
                    self.assertIn('Initialiser la base',response.read().decode())
                with urllib.request.urlopen(base+'/api/initialization') as response:
                    self.assertEqual(json.load(response)['state'],'idle')
                with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(base+'/api/stats')
                self.assertEqual(caught.exception.code,503)
                request=urllib.request.Request(base+'/api/initialize',data=b'{}',headers={'Content-Type':'application/json','Origin':'https://untrusted.example'})
                with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(request)
                self.assertEqual(caught.exception.code,403)
                with patch.object(job,'_run'):
                    request=urllib.request.Request(base+'/api/initialize',data=b'{}',headers={'Content-Type':'application/json','Origin':base})
                    with urllib.request.urlopen(request) as response:self.assertEqual(json.load(response)['state'],'running')
                    with self.assertRaises(ValueError):job.start()
            finally:http.shutdown();http.server_close();thread.join()

if __name__=='__main__':unittest.main()
