"""Vérifie la vraie boucle du panneau avec des fenêtres de jeu simulées."""
import copy,json,tempfile,threading,time
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from unittest.mock import patch
import CoordinationFenetres as coordination
import FenetresWakfu as geometry
import SwitcheurWakfu as app
from test_coordination_fenetres import FakeAPI

def run():
    api=FakeAPI();crash=threading.Event();workers=[];checks=[];errors=[]
    with tempfile.TemporaryDirectory(dir=app.ROOT,prefix='verification-cycle-') as temporary:
        qaRoot=Path(temporary)
        def fake_worker(events,stop,live):
            generation=len(workers)+1;workers.append(threading.current_thread())
            events.put({'type':'ready'});events.put({'type':'combat','actif':False,'combats':[]})
            while not stop.wait(.015):
                if generation==1 and crash.is_set():
                    events.put({'type':'error','message':'Une instance WAKFU a été fermée.'});break
            events.put({'type':'stopped'})
        def hook(root,actions,state):
            root.withdraw();stage=0;deadline=time.monotonic()+12
            def verify():
                nonlocal stage
                try:
                    assert time.monotonic()<deadline,'La relance ne termine pas.'
                    value=state()
                    if stage==0 and value['ready']:
                        assert value['status']=='Automatique actif'
                        checks.append('Détection active affichée');crash.set();stage=1
                    elif stage==1 and value['error'] and not value['thread'].is_alive():
                        stage=2;root.after(350,verify);return
                    elif stage==2:
                        assert value['error'] and value['status']=='Automatique arrêté'
                        assert value['issue']=='Une instance WAKFU a été fermée.'
                        checks.append('Erreur conservée après l’arrêt du flux')
                        entry=api.entries.pop(2);entry['handle']=8;api.entries[8]=entry;api.positions[8]=api.positions.pop(2)
                        actions['restart']();stage=3
                    elif stage==3 and len(workers)==2 and value['ready'] and not value['error']:
                        assert value['enabled'] and value['status']=='Automatique actif'
                        published=json.loads(coordination.STATUS.read_text(encoding='utf-8'))
                        assert '8' in published['P'] and '2' not in published['P']
                        assert not workers[0].is_alive()
                        checks.append('Relance avec le nouvel identifiant et aucun ancien flux actif')
                        actions['pause']();assert state()['status']=='Automatique en pause'
                        actions['restart']();stage=4
                    elif stage==4 and len(workers)==3 and value['ready']:
                        assert not value['enabled'] and value['status']=='Automatique en pause'
                        assert not workers[1].is_alive();checks.append('Pause volontaire conservée après relance')
                        root.deiconify();root.update_idletasks()
                        buttons=value['buttons']
                        for button in buttons.winfo_children():assert button.winfo_x()+button.winfo_width()<=buttons.winfo_width()
                        checks.append('Les quatre boutons restent accessibles dans le panneau')
                        actions['close']();return
                except Exception as ex:errors.append(str(ex));actions['close']();return
                root.after(60,verify)
            root.after(100,verify)
        with patch.object(app,'ROOT',qaRoot),patch.object(geometry,'ROOT',qaRoot),patch.multiple(coordination,ROOT=qaRoot,CONTROL=qaRoot/'control',STATUS=qaRoot/'control'/'switcher.json'):
            app.main(disposition_factory=lambda:geometry.Disposition(api),capture_worker=fake_worker,test_hook=hook)
        assert not errors,errors
        assert all(not thread.is_alive() for thread in workers),'Un flux de détection reste actif après fermeture.'
        checks.append('Fermeture complète des flux et du panneau')
    report={'resultat':'OK','verifications':checks}
    (app.ROOT/'verification-cycle-switcheur.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':run()
