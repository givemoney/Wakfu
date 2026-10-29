"""Diagnostic passif : journaux existants + audio Windows par instance."""
import ctypes as C
from ctypes import wintypes as W
import json,msvcrt,os,queue,re,sys,threading,time,wave
from pathlib import Path
import numpy as np
import tkinter as tk
from tkinter import ttk

ROOT=Path(__file__).resolve().parent
LOG=Path(os.environ['APPDATA'])/'zaap/gamesLogs/wakfu/logs/wakfu.log'
REFERENCE=ROOT/'assets/tour.npy'
DLL=C.CDLL(str(ROOT/'WakfuAudioCapture-v3.dll'))
DLL.AudioClock.restype=C.c_longlong
DLL.StartRecording.argtypes=[W.DWORD,W.LPCWSTR,C.c_longlong,C.POINTER(C.c_int)]
DLL.StartRecording.restype=C.c_void_p
DLL.StopRecording.argtypes=[C.c_void_p];DLL.StopRecording.restype=C.c_int
DLL.StartLiveCapture.argtypes=[W.DWORD,C.c_longlong,C.POINTER(C.c_int)];DLL.StartLiveCapture.restype=C.c_void_p
DLL.ReadLiveCapture.argtypes=[C.c_void_p,C.POINTER(C.c_short),C.c_int];DLL.ReadLiveCapture.restype=C.c_int
USER=C.WinDLL('user32',use_last_error=True)
USER.GetWindowTextLengthW.argtypes=[W.HWND];USER.GetWindowTextW.argtypes=[W.HWND,W.LPWSTR,C.c_int]
USER.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]
USER.IsWindowVisible.argtypes=[W.HWND]
ENUM=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
USER.EnumWindows.argtypes=[ENUM,W.LPARAM]
KERNEL=C.WinDLL('kernel32',use_last_error=True)
KERNEL.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE]
KERNEL.CreateFileW.restype=W.HANDLE

def windows():
    found={}
    @ENUM
    def visit(hwnd,param):
        if not USER.IsWindowVisible(hwnd):return True
        n=USER.GetWindowTextLengthW(hwnd);b=C.create_unicode_buffer(n+1);USER.GetWindowTextW(hwnd,b,n+1)
        if b.value.endswith(' - WAKFU') and USER.IsWindowVisible(hwnd):
            pid=W.DWORD();USER.GetWindowThreadProcessId(hwnd,C.byref(pid));found[pid.value]=b.value[:-8]
        return True
    USER.EnumWindows(visit,0)
    return found

def shared_file(path):
    h=KERNEL.CreateFileW(str(path),0x80000000,7,None,3,0x80,None)
    if h==C.c_void_p(-1).value:raise C.WinError(C.get_last_error())
    fd=msvcrt.open_osfhandle(h,os.O_RDONLY|os.O_BINARY)
    return os.fdopen(fd,'rb',buffering=0)

def shared_log():return shared_file(LOG)

class Fights:
    def __init__(self,names):self.names=set(names);self.active={};self.ended=set()
    def feed(self,line):
        end=re.search(r'End fight with id (\d+)',line)
        if end:
            fid=end[1];self.active.pop(fid,None);self.ended.add(fid);return
        entry=re.search(r'fightId=(\d+) (.*?) breed\s*:',line)
        if entry and entry[1] not in self.ended and entry[2] in self.names:
            self.active.setdefault(entry[1],set()).add(entry[2])

class Matcher:
    def __init__(self,template):
        self.t=template-template.mean();self.energy=float(self.t@self.t);self.m=len(template)
        self.tail=np.empty(0);self.consumed=0;self.last=-100.;self.spectra={};self.best_score=0.
    def feed(self,samples):
        if not len(samples):return None
        x=np.concatenate((self.tail,samples));offset=self.consumed-len(self.tail);self.consumed+=len(samples)
        self.tail=x[-(self.m-1):].copy()
        if len(x)<self.m or float(x@x)<self.energy*.002:return None
        n=1<<((len(x)+self.m-1).bit_length())
        if n not in self.spectra:self.spectra[n]=np.fft.rfft(self.t[::-1],n)
        dot=np.fft.irfft(np.fft.rfft(x,n)*self.spectra[n],n)[self.m-1:len(x)]
        s=np.empty(len(x)+1);s[0]=0;np.cumsum(x,out=s[1:])
        sq=np.empty(len(x)+1);sq[0]=0;np.cumsum(x*x,out=sq[1:])
        energy=np.maximum(sq[self.m:]-sq[:-self.m]-(s[self.m:]-s[:-self.m])**2/self.m,0)
        scores=dot/np.sqrt(np.maximum(energy*self.energy,1e-20));scores[energy<self.energy*.002]=0
        i=int(np.argmax(scores));at=(offset+i)/(44100/8);score=float(scores[i]);self.best_score=max(self.best_score,score)
        if score>=.65 and at-self.last>1.5:self.last=at;return at,score
        return None

def template():
    return np.load(str(REFERENCE),allow_pickle=False)

def worker(events,stop,live=False):
    captures=[];log=None;trace=None
    try:
        games=windows()
        if not games:raise RuntimeError('Aucune fenêtre WAKFU trouvée. Ouvre les quatre instances puis relance le diagnostic.')
        session=ROOT/'diagnostic-direct'/time.strftime('%Y%m%d-%H%M%S');session.mkdir(parents=True,exist_ok=True)
        trace=(session/'evenements.jsonl').open('w',encoding='utf-8')
        def emit(kind,**data):
            item={'type':kind,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**data};trace.write(json.dumps(item,ensure_ascii=False)+'\n');trace.flush();events.put(item)
        emit('setup',instances=games,dossier=str(session))
        tracker=Fights(games.values());log=shared_log();pending=b''
        # Reconstruct a fight already in progress; do not replay old audio events.
        initial=log.read()
        parts=initial.split(b'\n');pending=parts.pop()
        for line in parts:tracker.feed(line.decode('utf-8',errors='replace'))
        previous=None;epoch=DLL.AudioClock();ref=template()
        for pid,name in games.items():
            error=C.c_int();p=session/(str(pid)+'.wav')
            handle=DLL.StartLiveCapture(pid,epoch,C.byref(error)) if live else DLL.StartRecording(pid,str(p),epoch,C.byref(error))
            if not handle:raise RuntimeError('Capture audio impossible pour '+name+' : 0x'+format(error.value&0xffffffff,'08X'))
            captures.append({'handle':handle,'path':p,'pid':pid,'name':name,'pos':44,'matcher':Matcher(ref),'buffer':np.empty(44100*2,dtype=np.int16),'missing_since':None,'peak':0.,'squares':0.,'samples':0})
        log_identity=LOG.stat().st_ino
        started=time.monotonic();ready=False;heartbeat=started
        while not stop.is_set():
            if not live and time.monotonic()-started>1200:emit('message',message='Arrêt automatique après 20 minutes.');break
            st=LOG.stat()
            if st.st_ino!=log_identity or st.st_size<log.tell():
                log.close();log=shared_log();pending=b'';log_identity=st.st_ino
                emit('message',message='Rotation du journal détectée ; suivi repris.')
            current_names=windows();tracker.names.update(current_names.values())
            pending+=log.read();parts=pending.split(b'\n');pending=parts.pop()
            for line in parts:tracker.feed(line.decode('utf-8',errors='replace'))
            state=tuple(sorted(tracker.active))
            if state!=previous:emit('combat',actif=bool(state),combats=state);previous=state
            for cap in captures:
                cap['name']=current_names.get(cap['pid'],cap['name'])
                if cap['pid'] not in current_names:
                    if cap['missing_since'] is None:cap['missing_since']=time.monotonic()
                    if time.monotonic()-cap['missing_since']>2:raise RuntimeError('Une instance WAKFU a été fermée. Relance le panneau après avoir rouvert tes fenêtres.')
                else:cap['missing_since']=None
                if live:
                    buf=cap['buffer'];n=DLL.ReadLiveCapture(cap['handle'],buf.ctypes.data_as(C.POINTER(C.c_short)),len(buf))
                    if n<0:raise RuntimeError('Flux audio interrompu : 0x'+format(n&0xffffffff,'08X'))
                    if n==0:continue
                    stereo=buf[:n].reshape(-1,2);byte_count=n*2
                else:
                    with shared_file(cap['path']) as f:
                        f.seek(cap['pos']);raw=f.read();raw=raw[:len(raw)//32*32]
                    if not raw:continue
                    stereo=np.frombuffer(raw,dtype='<i2').reshape(-1,2);byte_count=len(raw)
                cap['pos']+=byte_count
                mono=stereo[::8].mean(axis=1,dtype=np.float64)/32768
                cap['peak']=max(cap['peak'],float(np.max(np.abs(mono))))
                cap['squares']+=float(mono@mono);cap['samples']+=len(mono)
                match=cap['matcher'].feed(mono)
                if match:
                    at,score=match;emit('tour',instance=cap['name'],pid=cap['pid'],similarite=round(score,3),seconde=round(at,3),combat_confirme=bool(state),monotonic=time.monotonic())
            if not ready:emit('ready',message='Capture audio initialisée — attente des sons de tour');ready=True
            if time.monotonic()-heartbeat>=5:
                audio={str(cap['pid']):{'nom':cap['name'],'pic_db':round(20*np.log10(max(cap['peak'],1e-10)),1),'rms_db':round(10*np.log10(max(cap['squares']/max(cap['samples'],1),1e-20)),1),'meilleure_similarite':round(cap['matcher'].best_score,3)} for cap in captures}
                emit('heartbeat',message='Diagnostic actif',audio_octets={cap['name']:cap['pos']-44 for cap in captures},audio=audio,combats=state)
                for cap in captures:cap['peak']=0.;cap['squares']=0.;cap['samples']=0;cap['matcher'].best_score=0.
                heartbeat=time.monotonic()
            stop.wait(.06)
    except Exception as ex:
        item={'type':'error','message':str(ex)}
        if trace:trace.write(json.dumps(item,ensure_ascii=False)+'\n');trace.flush()
        events.put(item)
    finally:
        for cap in captures:
            hr=DLL.StopRecording(cap['handle'])
            if hr<0:events.put({'type':'error','message':'Capture audio interrompue : 0x'+format(hr&0xffffffff,'08X')})
        if log:log.close()
        if trace:trace.close()
        events.put({'type':'stopped'})

def main():
    root=tk.Tk();root.title('WAKFU — détecteur de combat et de tour');root.geometry('720x450')
    q=queue.Queue();stop=threading.Event();closing=False;thread=None;folder=None;failed=False;state_known=False
    status=tk.StringVar(value='Démarrage du diagnostic…');turn=tk.StringVar(value='Tour : en attente');detail=tk.StringVar(value='Lecture seule — aucune fenêtre déplacée, aucune touche envoyée.')
    ttk.Label(root,textvariable=status,font=('Segoe UI',21,'bold')).pack(anchor='w',padx=18,pady=(15,5))
    ttk.Label(root,textvariable=turn,font=('Segoe UI',17)).pack(anchor='w',padx=18,pady=5)
    ttk.Label(root,textvariable=detail,wraplength=680).pack(anchor='w',padx=18,pady=8)
    history=tk.Text(root,height=11,state='disabled',font=('Consolas',10));history.pack(fill='both',expand=True,padx=18,pady=8)
    controls=ttk.Frame(root);controls.pack(fill='x',padx=18,pady=(0,15))
    def add(text):history.configure(state='normal');history.insert('end',time.strftime('%H:%M:%S')+'  '+text+'\n');history.see('end');history.configure(state='disabled')
    def halt():stop.set();status.set('Arrêt du diagnostic…')
    ttk.Button(controls,text='Arrêter le diagnostic',command=halt).pack(side='left')
    ttk.Button(controls,text='Voir les résultats',command=lambda:os.startfile(folder) if folder else None).pack(side='left',padx=10)
    def close():
        nonlocal closing
        closing=True;stop.set();status.set('Finalisation des pistes audio…')
    root.protocol('WM_DELETE_WINDOW',close)
    def update():
        nonlocal folder,failed,state_known
        try:
            while True:
                e=q.get_nowait();kind=e['type']
                if kind=='setup':folder=e['dossier'];add('Instances : '+', '.join(e['instances'].values()))
                elif kind=='ready':add(e['message']);detail.set('Fais un combat : le statut et le compte actif doivent suivre tes tours.')
                elif kind=='combat':
                    status.set('En combat' if e['actif'] else 'Hors combat');turn.set('Tour : en attente' if e['actif'] else 'Tour : aucun');add('Combat(s) : '+', '.join(e['combats']) if e['actif'] else ('Fin de combat — retour hors combat' if state_known else 'Aucun combat suivi dans le journal'));state_known=True
                elif kind=='tour':
                    turn.set('Tour de : '+e['instance']);add(e['instance']+' — ressemblance '+str(round(e['similarite']*100))+' %'+('' if e['combat_confirme'] else ' — combat non confirmé dans les logs'))
                elif kind=='error':failed=True;status.set('Diagnostic interrompu — erreur');detail.set(e['message']);add('Erreur : '+e['message'])
                elif kind=='heartbeat':detail.set('Diagnostic actif — dernière vérification à '+time.strftime('%H:%M:%S')+'. Fais un combat pour tester les tours.')
                elif kind=='message':add(e['message'])
                elif kind=='stopped':
                    if closing:root.destroy();return
                    if not failed:status.set('Diagnostic arrêté')
                    add('Diagnostic terminé.' if failed else 'Fichiers enregistrés. Ferme et relance pour un nouveau test.')
        except queue.Empty:pass
        if closing and thread is not None and not thread.is_alive():root.destroy();return
        root.after(100,update)
    thread=threading.Thread(target=worker,args=(q,stop),daemon=False);thread.start();root.after(100,update);root.mainloop()

def selftest():
    ref=template();m=Matcher(ref);x=np.r_[np.zeros(3000),ref,np.zeros(3000)];detections=[]
    for i in range(0,len(x),662):
        r=m.feed(x[i:i+662])
        if r:detections.append(r)
    assert len(detections)==1 and detections[0][1]>.99,detections
    assert Matcher(ref).feed(np.zeros(10000)) is None
    f=Fights(['Hadak Lkelb']);line='fightId=123 Hadak Lkelb breed : 4 join the fight'
    f.feed(line);f.feed(line);assert len(f.active)==1
    f.feed('fightId=456 Hadak Lkelb breed : 4 join the fight');f.feed('End fight with id 123');assert set(f.active)=={'456'}
    f.feed(line);assert set(f.active)=={'456'}
    f.feed('End fight with id 456');assert not f.active
    print('OK : détection progressive, silence, doublons et combats simultanés.')

if __name__=='__main__':
    if '--selftest' in sys.argv:selftest()
    else:main()
