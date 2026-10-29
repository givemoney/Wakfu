"""Swaps déclenchés uniquement par les boutons du panneau de commandes."""
import ctypes as C,json,sys,time
from pathlib import Path
from FenetresWakfu import Disposition,ROOT,WindowsAPI,USER,same_rect
from CoordinationFenetres import request,write

NAMES=('Roubouze Yabess','Abouk Imak','Naheulbeuuk')
def controller(state,strict=True):
    d=Disposition();d.p={int(pid):e for pid,e in state['P'].items()};d.main=int(state['principal']);d.current=int(state['cible']) if state['active'] else d.main
    if strict and not all(d.api.valid(pid,e) for pid,e in d.p.items()):raise RuntimeError('Les instances ont changé. Rouvre Wakfu commandes avec tes quatre fenêtres ouvertes.')
    d.enabled=True;return d
def verify(d):
    for tick in range(8):
        for pid,entry in d.p.items():
            slot=d.p[d.current] if pid==d.main and d.current!=d.main else d.p[d.main] if pid==d.current and pid!=d.main else entry
            if not same_rect(d.api.rectangle(entry),slot['rect']):raise RuntimeError('La fenêtre '+entry['name']+' n’a pas conservé son emplacement.')
        time.sleep(.025)

def run(action,folder,index=None):
    state_path=folder/'etat.json';result={'ok':False,'active':False,'message':''}
    reservation=None
    state=json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else None
    if state:result['active']=bool(state['active'])
    try:
        if action=='swap':
            if state and state['active']:raise RuntimeError('Reviens à P avant de choisir une autre fenêtre.')
            if index not in range(len(NAMES)):raise RuntimeError('Compte de destination inconnu.')
            reservation=request('reserve',folder)
            if reservation:
                state={'active':False,'principal':reservation['principal'],'cible':reservation['principal'],'P':reservation['P'],'auto_resume':reservation['resume']}
                write(state_path,state)
            snap=WindowsAPI().snapshot()
            if len(snap)!=4:raise RuntimeError('Ouvre les quatre fenêtres WAKFU avant de faire un swap.')
            if reservation:
                baseline={int(pid):entry for pid,entry in reservation['P'].items()}
                main=int(reservation['principal'])
                if set(snap)!=set(baseline):raise RuntimeError('Les instances ont changé depuis la mémorisation de P.')
            else:
                mains=[pid for pid,e in snap.items() if e['primary']]
                if len(mains)!=1:raise RuntimeError('Place uniquement ton compte principal sur l’écran principal, puis réessaie.')
                main=mains[0];baseline=snap
            targets=[pid for pid,e in snap.items() if e['name']==NAMES[index]]
            if len(targets)!=1 or targets[0]==main:raise RuntimeError('La fenêtre '+NAMES[index]+' est introuvable ou déjà principale.')
            state={'active':False,'principal':main,'cible':targets[0],'P':baseline,'auto_resume':reservation['resume'] if reservation else True}
            write(state_path,state);d=controller(state)
            # Persist recovery information before the first movement.
            state['active']=True;write(state_path,state)
            try:
                focused=d.turn(targets[0],True);verify(d)
            except Exception:
                try:d.restore(focus=True);state['active']=False;write(state_path,state)
                except Exception:pass
                raise
            result={'ok':True,'active':True,'focused':bool(focused),'message':NAMES[index]+' sur l’écran principal. Retour à P pour choisir un autre compte.'+('\nAutomatique suspendu pendant cet échange.' if reservation else '')}
        elif action=='return':
            if not state or not state['active']:return {'ok':True,'active':False,'message':'Disposition P déjà active.'}
            reservation=request('reserve',folder)
            if reservation and (int(reservation['principal'])!=int(state['principal']) or {int(pid) for pid in reservation['P']}!={int(pid) for pid in state['P']}):raise RuntimeError('Les instances du switcher ont changé. Relance les panneaux avec tes quatre fenêtres ouvertes.')
            d=controller(state,False);remaining={pid:e for pid,e in d.p.items() if d.api.valid(pid,e)}
            try:d.restore(focus=True)
            except Exception:
                if not all(same_rect(d.api.rectangle(e),e['rect']) for e in remaining.values()):raise
            if len(remaining)==4:verify(d)
            released=request('release',folder)
            state['active']=False;write(state_path,state)
            result={'ok':True,'active':False,'message':'Position P restaurée. '+d.p[d.main]['name']+' sur l’écran principal.'+('\nAutomatique repris.' if released and released['enabled'] else '\nAutomatique conservé en pause.' if released else '')}
        else:raise RuntimeError('Commande de déplacement inconnue.')
    except Exception as ex:
        if action=='swap' and reservation and state and not state['active']:
            try:request('release',folder)
            except Exception as release_error:
                state['active']=True;write(state_path,state)
                ex=RuntimeError(str(ex)+' Reviens à P pour terminer : '+str(release_error))
        if state_path.exists():result['active']=bool(json.loads(state_path.read_text(encoding='utf-8'))['active'])
        result['message']=str(ex)
    return result

if __name__=='__main__':
    USER.FindWindowW.argtypes=[C.c_wchar_p,C.c_wchar_p];USER.FindWindowW.restype=C.c_void_p
    action=sys.argv[1];folder=Path(sys.argv[2]).resolve()
    allowed=(ROOT/'manual-commandes').resolve()
    if not folder.is_relative_to(allowed):raise RuntimeError('Dossier de session invalide.')
    folder.mkdir(parents=True,exist_ok=True)
    value=run(action,folder,int(sys.argv[3]) if len(sys.argv)>3 else None)
    write(folder/'resultat.json',value)
    sys.exit(0 if value['ok'] else 1)
