import copy
import ctypes as C
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from unittest.mock import patch
import CoordinationFenetres as coordination
import CommandesSwap as commands
from FenetresWakfu import Disposition

class FakeAPI:
    def __init__(self):
        names=['Hadak Lkelb',*commands.NAMES]
        self.entries={i:{'handle':i,'name':name,'primary':i==0,'rect':[i*100,0,(i+1)*100,80]} for i,name in enumerate(names)}
        self.positions={i:list(e['rect']) for i,e in self.entries.items()}
        self.fail_next=False
    def valid(self,pid,entry):return pid in self.entries
    def snapshot(self):
        found=copy.deepcopy(self.entries)
        for pid,e in found.items():e['rect']=list(self.positions[pid]);e['primary']=e['rect']==self.entries[0]['rect']
        return found
    def place(self,entry,slot):
        if self.fail_next and entry['handle']==1 and slot['rect']==self.entries[0]['rect']:
            self.fail_next=False;raise RuntimeError('Test: déplacement refusé')
        self.positions[entry['handle']]=list(slot['rect'])
    def rectangle(self,entry):return self.positions[entry['handle']]
    def focus(self,entry):return True

class FakeUser:
    def FindWindowW(self,*args):return 123
    def GetWindowThreadProcessId(self,handle,pid):pid._obj.value=os.getpid();return 1

class CoordinationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=coordination.ROOT,prefix='test-coordination-')
        self.root=Path(self.temp.name);self.owner=self.root/'manual-commandes'/'panel';self.owner.mkdir(parents=True)
        self.paths=patch.multiple(coordination,ROOT=self.root,CONTROL=self.root/'control',STATUS=self.root/'control'/'switcher.json');self.paths.start()
        self.api=FakeAPI();self.d=Disposition(self.api);self.d.p=copy.deepcopy(self.api.entries);self.d.main=self.d.current=0;self.d.enabled=True
        self.control=coordination.ManualControl(self.d)
        self.patch_api=patch.object(commands,'WindowsAPI',return_value=self.api);self.patch_api.start()
        self.patch_disposition=patch.object(commands,'Disposition',side_effect=lambda:Disposition(self.api));self.patch_disposition.start()
        def request(action,owner):return self.control.reserve(owner) if action=='reserve' else self.control.release(owner)
        self.patch_request=patch.object(commands,'request',side_effect=request);self.patch_request.start()
    def tearDown(self):
        self.patch_request.stop();self.patch_disposition.stop();self.patch_api.stop();self.paths.stop();self.temp.cleanup()
    def test_manual_swap_uses_P_when_auto_already_swapped(self):
        self.d.turn(2,True)
        result=commands.run('swap',self.owner,0)
        self.assertTrue(result['ok']);self.assertFalse(self.d.enabled)
        self.assertEqual(self.api.positions,{0:self.d.p[1]['rect'],1:self.d.p[0]['rect'],2:self.d.p[2]['rect'],3:self.d.p[3]['rect']})
        before=copy.deepcopy(self.api.positions);self.d.turn(3,True);self.d.finish();self.d.check()
        self.assertEqual(self.api.positions,before)
        state=json.loads((self.owner/'etat.json').read_text(encoding='utf-8'))
        self.assertEqual(state['P']['0']['rect'],self.d.p[0]['rect'])
        blocked=commands.run('swap',self.owner,1);self.assertFalse(blocked['ok']);self.assertTrue(blocked['active'])
        result=commands.run('return',self.owner)
        self.assertTrue(result['ok']);self.assertFalse(result['active']);self.assertTrue(self.d.enabled)
        self.assertIsNone(self.control.owner);self.assertEqual(self.api.positions,{i:e['rect'] for i,e in self.d.p.items()})
        self.d.turn(3,True);self.assertEqual(self.d.current,3)
    def test_explicit_auto_pause_preserved(self):
        self.d.enabled=False
        self.assertTrue(commands.run('swap',self.owner,1)['ok'])
        self.assertTrue(commands.run('return',self.owner)['ok'])
        self.assertFalse(self.d.enabled)
    def test_failed_swap_restores_and_releases(self):
        self.api.fail_next=True
        result=commands.run('swap',self.owner,0)
        self.assertFalse(result['ok']);self.assertFalse(result['active'])
        self.assertTrue(self.d.enabled);self.assertIsNone(self.control.owner)
        self.assertEqual(self.api.positions,{i:e['rect'] for i,e in self.d.p.items()})
    def test_second_panel_cannot_take_control(self):
        self.control.reserve(self.owner)
        with self.assertRaises(RuntimeError):self.control.reserve(self.root/'manual-commandes'/'other')
        with self.assertRaises(RuntimeError):self.control.release(self.root/'manual-commandes'/'other')
        self.assertEqual(self.control.owner,str(self.owner))
    def test_validation_failure_releases_reservation(self):
        self.api.entries[1]['name']='Compte renommé'
        result=commands.run('swap',self.owner,0)
        self.assertFalse(result['ok']);self.assertFalse(result['active'])
        self.assertTrue(self.d.enabled);self.assertIsNone(self.control.owner)
    def test_return_with_closed_instance_keeps_auto_paused(self):
        self.assertTrue(commands.run('swap',self.owner,0)['ok'])
        del self.api.entries[3]
        result=commands.run('return',self.owner)
        self.assertTrue(result['ok']);self.assertFalse(result['active']);self.assertFalse(self.d.enabled)
        self.assertIsNone(self.control.owner)
    def test_release_failure_keeps_return_available(self):
        self.assertTrue(commands.run('swap',self.owner,0)['ok'])
        def fail_release(action,owner):
            if action=='release':raise RuntimeError('Test: réponse retardée')
            return self.control.reserve(owner)
        with patch.object(commands,'request',side_effect=fail_release):
            result=commands.run('return',self.owner)
        self.assertFalse(result['ok']);self.assertTrue(result['active']);self.assertFalse(self.d.enabled)
        result=commands.run('return',self.owner)
        self.assertTrue(result['ok']);self.assertFalse(result['active']);self.assertTrue(self.d.enabled)
    def test_restart_preserves_active_manual_swap(self):
        self.assertTrue(commands.run('swap',self.owner,2)['ok'])
        before=copy.deepcopy(self.api.positions)
        replacement=coordination.ManualControl(Disposition(self.api))
        self.assertTrue(replacement.recover_manual());self.assertFalse(replacement.d.enabled)
        self.assertEqual(replacement.d.main,0);self.assertEqual(self.api.positions,before)
        self.control=replacement
        self.assertTrue(commands.run('return',self.owner)['ok']);self.assertTrue(replacement.d.enabled)
    def test_release_refuses_unrestored_windows(self):
        self.control.reserve(self.owner);self.api.positions[1]=[0,0,100,80]
        with self.assertRaises(RuntimeError):self.control.release(self.owner)
        self.assertFalse(self.d.enabled);self.assertEqual(self.control.owner,str(self.owner))
    def test_request_reply_protocol(self):
        self.control.publish();stop=threading.Event();errors=[]
        def serve():
            while not stop.is_set():
                try:self.control.poll()
                except Exception as ex:errors.append(ex);break
                stop.wait(.01)
        thread=threading.Thread(target=serve);thread.start()
        try:
            with patch.object(coordination,'USER',FakeUser()):
                result=coordination.request('reserve',self.owner)
                self.assertTrue(result['ok']);self.assertFalse(self.d.enabled)
                result=coordination.request('release',self.owner)
                self.assertTrue(result['enabled'])
        finally:stop.set();thread.join(2)
        self.assertEqual(errors,[])
    def test_expired_request_cannot_pause_later(self):
        coordination.write(self.control.folder/'request-expired.json',{'id':'expired','action':'reserve','owner':str(self.owner),'deadline':0})
        results=self.control.poll()
        self.assertFalse(results[0][1]['ok']);self.assertTrue(self.d.enabled);self.assertIsNone(self.control.owner)

if __name__=='__main__':unittest.main(verbosity=2)
