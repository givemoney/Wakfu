import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import server

class LearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        with closing(sqlite3.connect(self.root/'wakfu.sqlite')) as db, db:
            db.executescript('CREATE TABLE all_items(id INTEGER); INSERT INTO all_items VALUES(1),(2); CREATE TABLE item_learning(id INTEGER,learn_furniture INTEGER); INSERT INTO item_learning VALUES(1,1),(2,0);')
        self.patches=[patch.object(server,'ROOT',self.root),patch.object(server,'PERSONAL',self.root/'personal.sqlite')]
        for p in self.patches:p.start()
        server.initialize_personal()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def test_toggle_preserves_notes_and_favorites(self):
        initial=server.save_preference({'item_id':1,'note':'test','favorite':True})
        self.assertFalse(initial['learned'])
        checked=server.save_preference({'item_id':1,'learned':True})
        self.assertTrue(checked['learned'])
        self.assertEqual(checked['note'],'test')
        self.assertTrue(checked['favorite'])
        server.initialize_personal()
        with closing(sqlite3.connect(server.PERSONAL)) as db, db:self.assertEqual(db.execute('SELECT learned FROM item_preferences WHERE item_id=1').fetchone()[0],1)
        self.assertFalse(server.save_preference({'item_id':1,'learned':False})['learned'])
    def test_nonlearnable_rejected(self):
        with self.assertRaises(ValueError):server.save_preference({'item_id':2,'learned':True})
    def test_boolean_required(self):
        with self.assertRaises(ValueError):server.save_preference({'item_id':1,'learned':'true'})
    def test_migration_preserves_existing_data(self):
        with closing(sqlite3.connect(server.PERSONAL)) as db, db:
            db.execute('DROP TABLE item_preferences')
            db.executescript("CREATE TABLE item_preferences(item_id INTEGER PRIMARY KEY,note TEXT,favorite INTEGER); INSERT INTO item_preferences VALUES(1,'kept',1);")
        server.initialize_personal()
        with closing(sqlite3.connect(server.PERSONAL)) as db, db:self.assertEqual(db.execute('SELECT note,favorite,learned FROM item_preferences').fetchone(),('kept',1,0))
if __name__=='__main__':unittest.main()
