"""Exercise automatic geometry recovery through the real Tk event loop."""
import json,tempfile,threading,time,sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'))
import CoordinationFenetres as coordination
import FenetresWakfu as geometry
import SwitcheurWakfu as app
from test_coordination_fenetres import FakeAPI

api=FakeAPI();events=[];threads=[];failures=[0];errors=[];checks=[]
original_place=api.place
def place(entry,slot):
    if entry['handle']==1 and failures[0]>0:
        failures[0]-=1;raise geometry.PlacementError('Test: Java redimensionne encore la fenetre')
    original_place(entry,slot)
api.place=place
def worker(queue,stop,live):
    events.append(queue);threads.append(threading.current_thread())
    queue.put({'type':'ready'});queue.put({'type':'combat','actif':False,'combats':[]})
    stop.wait();queue.put({'type':'stopped'})
def hook(root,actions,state):
    root.withdraw();stage=0;due=0;deadline=time.monotonic()+10;seen_recovery=False
    def check():
        nonlocal stage,due,seen_recovery
        try:
            assert time.monotonic()<deadline,'Automatic recovery timed out'
            value=state()
            if stage==0 and value['ready']:
                api.positions[1]=[120,0,220,80];due=time.monotonic()+.7;stage=1
            elif stage==1 and time.monotonic()>=due:
                assert api.positions[1]==[120,0,220,80] and not value['error']
                checks.append('Aucun redimensionnement impose hors combat')
                events[0].put({'type':'combat','actif':True,'combats':['test']})
                events[0].put({'type':'tour','pid':1,'instance':'Roubouze Yabess','combat_confirme':True,'monotonic':time.monotonic(),'similarite':.95})
                stage=2
            elif stage==2 and api.positions[1]==api.entries[0]['rect']:
                failures[0]=2;api.positions[1]=[20,10,120,90];stage=3
            elif stage==3:
                if value['status']=='Réajustement des fenêtres…':seen_recovery=True
                if seen_recovery and not value['error'] and value['enabled']:
                    assert failures[0]==0
                    assert api.positions[1]==api.entries[0]['rect']
                    assert api.positions[0]==api.entries[1]['rect']
                    assert len(threads)==1 and threads[0].is_alive()
                    checks.extend(['Reprise automatique apres deux retards de taille','Compte qui joue remis sur le principal','Flux audio conserve pendant la reprise'])
                    actions['close']();return
        except Exception as ex:errors.append(str(ex));actions['close']();return
        root.after(40,check)
    root.after(100,check)
with tempfile.TemporaryDirectory(dir=ROOT/'app',prefix='verification-reprise-') as temporary:
    qa=Path(temporary)
    with patch.object(app,'ROOT',qa),patch.object(geometry,'ROOT',qa),patch.multiple(coordination,ROOT=qa,CONTROL=qa/'control',STATUS=qa/'control'/'switcher.json'):
        app.main(disposition_factory=lambda:geometry.Disposition(api),capture_worker=worker,test_hook=hook)
assert not errors,errors
assert all(not thread.is_alive() for thread in threads)
result={'resultat':'OK','verifications':checks}
(ROOT/'code'/'verification-reprise.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
