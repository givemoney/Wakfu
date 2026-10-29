"""Coordination entre nos deux panneaux, sans accès au client du jeu."""
import ctypes as C
import json
import os
import time
import uuid
from pathlib import Path
from ctypes import wintypes as W
from FenetresWakfu import same_rect

ROOT=Path(__file__).resolve().parent
CONTROL=ROOT/'coordination-fenetres'
STATUS=CONTROL/'switcher.json'
TITLE='WAKFU — fenêtres de combat'
USER=C.WinDLL('user32',use_last_error=True)
USER.FindWindowW.argtypes=[C.c_wchar_p,C.c_wchar_p]
USER.FindWindowW.restype=W.HWND
USER.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        for attempt in range(10):
            try:temporary.replace(path);return
            except PermissionError:
                if attempt==9:raise
                time.sleep(.01)
    finally:
        temporary.unlink(missing_ok=True)

def owner_path(value):
    owner=Path(value).resolve()
    if not owner.is_relative_to((ROOT/'manual-commandes').resolve()):raise RuntimeError('Session de commandes invalide.')
    return str(owner)

def connection():
    handle=USER.FindWindowW(None,TITLE)
    if not handle:return None
    pid=W.DWORD();USER.GetWindowThreadProcessId(handle,C.byref(pid))
    try:state=json.loads(STATUS.read_text(encoding='utf-8'))
    except (OSError,ValueError):state={}
    run=state.get('run','')
    if state.get('pid')!=pid.value or len(run)!=32 or any(c not in '0123456789abcdef' for c in run):
        raise RuntimeError('Le switcher de combat doit être relancé pour permettre les swaps manuels.')
    return state

def request(action,owner,timeout=5):
    state=connection()
    if state is None:return None
    folder=CONTROL/state['run'];identifier=uuid.uuid4().hex
    reply=folder/('reply-'+identifier+'.json')
    write(folder/('request-'+identifier+'.json'),{'id':identifier,'action':action,'owner':owner_path(owner),'deadline':time.time()+timeout})
    deadline=time.monotonic()+timeout+.5
    while time.monotonic()<deadline:
        if reply.exists():
            result=json.loads(reply.read_text(encoding='utf-8'));reply.unlink(missing_ok=True)
            if not result['ok']:raise RuntimeError(result['message'])
            return result
        time.sleep(.04)
    # An acknowledgement can arrive late after a slow Windows placement.
    # Recover its published ownership instead of leaving an invisible pause.
    current=connection()
    if current and current['run']==state['run']:
        if action=='reserve' and current['owner']==owner_path(owner):
            return {'ok':True,'message':'Automatique suspendu.','principal':current['principal'],'P':current['P'],'resume':current['resume']}
        if action=='release' and current['owner'] is None:
            return {'ok':True,'message':'P restaurée.','enabled':current['enabled']}
    raise RuntimeError('Le switcher ne répond pas. Aucun swap supplémentaire n’a été effectué.')

class ManualControl:
    def __init__(self,disposition):
        self.d=disposition;self.owner=None;self.resume=False;self.resumed_at=0;self.health={}
        self.run=uuid.uuid4().hex;self.folder=CONTROL/self.run
        self.folder.mkdir(parents=True,exist_ok=True)

    def publish(self):
        write(STATUS,{'pid':os.getpid(),'run':self.run,'owner':self.owner,'enabled':self.d.enabled,'resume':self.resume,'principal':self.d.main,'P':self.d.p,**self.health})

    def reserve(self,owner):
        owner=owner_path(owner)
        if self.owner and self.owner!=owner:raise RuntimeError('Un autre échange manuel est actif. Reviens à P dans son panneau.')
        if not self.d.p:raise RuntimeError('Le switcher n’a pas encore mémorisé P.')
        if not self.owner:
            resume=self.d.enabled
            self.d.enabled=False
            self.d.restore()
            self.owner=owner;self.resume=resume
        return {'ok':True,'message':'Automatique suspendu pendant le swap manuel.','principal':self.d.main,'P':self.d.p,'resume':self.resume}

    def release(self,owner,allow_resume=True):
        owner=owner_path(owner)
        if not self.owner:return {'ok':True,'message':'Aucun échange manuel réservé.','enabled':self.d.enabled}
        if self.owner!=owner:raise RuntimeError('Cet échange appartient à un autre panneau de commandes.')
        valid=all(self.d.api.valid(pid,e) for pid,e in self.d.p.items())
        if valid and any(not same_rect(self.d.api.rectangle(e),e['rect']) for e in self.d.p.values()):
            raise RuntimeError('Restaure P avant de reprendre les échanges automatiques.')
        self.d.current=self.d.main;self.d.enabled=bool(self.resume and allow_resume and valid)
        self.resumed_at=time.monotonic()
        self.owner=None;self.resume=False
        return {'ok':True,'message':'P restaurée.','enabled':self.d.enabled}

    def poll(self,allow_resume=True):
        handled=[]
        for path in sorted(self.folder.glob('request-*.json')):
            data=json.loads(path.read_text(encoding='utf-8'))
            try:
                if time.time()>data['deadline']:raise RuntimeError('La demande de swap a expiré ; réessaie.')
                if data['action']=='reserve':result=self.reserve(data['owner'])
                elif data['action']=='release':result=self.release(data['owner'],allow_resume)
                else:raise RuntimeError('Demande de fenêtre inconnue.')
            except Exception as ex:result={'ok':False,'message':str(ex)}
            self.publish()
            write(self.folder/('reply-'+data['id']+'.json'),result)
            path.unlink(missing_ok=True)
            handled.append((data['action'],result))
        return handled

    def recover_manual(self):
        for path in sorted((ROOT/'manual-commandes').glob('*/etat.json'),key=lambda p:p.stat().st_mtime,reverse=True):
            try:
                state=json.loads(path.read_text(encoding='utf-8'))
                entries={int(pid):entry for pid,entry in state['P'].items()}
                main=int(state['principal'])
                if not state['active'] or len(entries)!=4 or main not in entries:continue
                if not all(self.d.api.valid(pid,e) for pid,e in entries.items()):continue
                self.d.p=entries;self.d.main=self.d.current=main;self.d.enabled=False
                self.owner=owner_path(path.parent);self.resume=bool(state.get('auto_resume',True))
                return True
            except (OSError,ValueError,KeyError):continue
        return False

    def close(self):
        try:
            current=json.loads(STATUS.read_text(encoding='utf-8'))
            if current.get('run')==self.run:STATUS.unlink(missing_ok=True)
        except (OSError,ValueError):pass
