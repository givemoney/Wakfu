import ctypes as C
import json
import queue
import threading
import time
import traceback
import tkinter as tk
from tkinter import ttk
from DetecteurTourWakfu import worker,ROOT,USER,KERNEL
from FenetresWakfu import Disposition,PlacementError
from CoordinationFenetres import ManualControl,TITLE

def main(disposition_factory=Disposition,capture_worker=worker,test_hook=None):
    KERNEL.CreateMutexW.argtypes=[C.c_void_p,C.c_int,C.c_wchar_p]
    KERNEL.CreateMutexW.restype=C.c_void_p
    KERNEL.CloseHandle.argtypes=[C.c_void_p]
    USER.FindWindowW.argtypes=[C.c_wchar_p,C.c_wchar_p]
    USER.FindWindowW.restype=C.c_void_p
    mutex=KERNEL.CreateMutexW(None,False,'Local\\WakfuBoardFenêtresCombat'+('-verification' if test_hook else ''))
    if not mutex:raise C.WinError()
    if C.get_last_error()==183:
        handle=USER.FindWindowW(None,TITLE)
        if handle:USER.ShowWindow(handle,9);USER.SetForegroundWindow(handle)
        KERNEL.CloseHandle(mutex)
        return
    try:USER.SetProcessDpiAwarenessContext(C.c_void_p(-4))
    except Exception:pass
    root=tk.Tk();root.title('Vérification du switcher' if test_hook else TITLE)
    root.geometry('800x590+40+40');root.minsize(760,550)
    disposition=disposition_factory();control=ManualControl(disposition)
    q=queue.Queue();stop=threading.Event();thread=None
    closing=False;restarting=False;combat=False;ready=False;had_error=False;last_error='';desired_enabled=True
    last_check=0;last_publish=0;labels={}
    recover_after=0;recovery_attempts=0;recovery_target=None
    folder=ROOT/'switcheur'/time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True,exist_ok=True)
    audit=(folder/'fenetres.jsonl').open('a',encoding='utf-8')
    status=tk.StringVar(value='Préparation…');phase=tk.StringVar(value='Combat : en attente')
    turn=tk.StringVar(value='Tour : en attente');mode=tk.StringVar(value='Position P : en préparation')
    hint=tk.StringVar(value='Ouvre les quatre jeux et place ton compte principal sur l’écran principal.')
    audio_state=tk.StringVar(value='Son : capture en préparation')
    activity=tk.StringVar(value='Détection : en préparation');choice=tk.StringVar();topmost=tk.BooleanVar(value=False)
    status_label=ttk.Label(root,textvariable=status,font=('Segoe UI',21,'bold'))
    status_label.pack(anchor='w',padx=18,pady=(15,4))
    ttk.Label(root,textvariable=phase,font=('Segoe UI',11)).pack(anchor='w',padx=18,pady=2)
    ttk.Label(root,textvariable=turn,font=('Segoe UI',16)).pack(anchor='w',padx=18,pady=4)
    ttk.Label(root,textvariable=mode).pack(anchor='w',padx=18,pady=3)
    mainrow=ttk.Frame(root);mainrow.pack(fill='x',padx=18,pady=5)
    ttk.Label(mainrow,text='Compte principal :').pack(side='left')
    combo=ttk.Combobox(mainrow,textvariable=choice,state='readonly',width=38)
    combo.pack(side='left',padx=10)
    ttk.Checkbutton(root,text='Garder ce panneau au premier plan',variable=topmost,
                    command=lambda:root.attributes('-topmost',topmost.get())).pack(anchor='w',padx=18,pady=3)
    ttk.Label(root,textvariable=hint,wraplength=760).pack(anchor='w',padx=18,pady=5)
    ttk.Label(root,textvariable=activity).pack(anchor='w',padx=18,pady=2)
    ttk.Label(root,textvariable=audio_state,wraplength=760).pack(anchor='w',padx=18,pady=2)
    buttons=ttk.Frame(root);buttons.pack(side='bottom',fill='x',padx=18,pady=(5,15))
    history=tk.Text(root,height=9,state='disabled',font=('Consolas',10))
    history.pack(fill='both',expand=True,padx=18,pady=8)

    def note(message,**data):
        audit.write(json.dumps({'heure':time.strftime('%Y-%m-%dT%H:%M:%S'),'message':message,**data},ensure_ascii=False)+'\n');audit.flush()
        history.configure(state='normal');history.insert('end',time.strftime('%H:%M:%S')+'  '+message+'\n')
        if int(history.index('end-1c').split('.')[0])>500:history.delete('1.0','100.0')
        history.see('end');history.configure(state='disabled')

    def refresh():
        if closing:state,text,color='closing','Désactivation…','#8a5700'
        elif restarting:state,text,color='starting','Relance de la détection…','#8a5700'
        elif recover_after:state,text,color='recovering','Réajustement des fenêtres…','#8a5700'
        elif had_error:state,text,color='error','Automatique arrêté','#a32525'
        elif control.owner:state,text,color='manual','Échange manuel en cours','#8a5700'
        elif not ready:state,text,color='starting','Préparation de la détection…','#8a5700'
        elif disposition.enabled:state,text,color='running','Automatique actif','#17713a'
        else:state,text,color='paused','Automatique en pause','#8a5700'
        status.set(text);status_label.configure(foreground=color)
        mode.set('Échange manuel : utilise Retour à P dans Wakfu commandes.' if control.owner else
                 'Position P mémorisée pour les quatre fenêtres.' if disposition.p else 'Position P non mémorisée.')
        phase.set('Combat en cours' if combat else 'Hors combat')
        disabled=closing or restarting or bool(control.owner) or bool(recover_after)
        for button in (pausebutton,restorebutton,memorizebutton):button.configure(state='disabled' if disabled or had_error or not ready else 'normal')
        restartbutton.configure(state='disabled' if disabled else 'normal')
        combo.configure(state='disabled' if disabled else 'readonly')
        pausebutton.configure(text='Suspendre' if disposition.enabled else 'Activer')
        control.health={'app_state':state,'status':text,'issue':last_error,'detecting':ready,'updated_utc':time.time()}
        control.publish()

    def failure(ex):
        nonlocal had_error,last_error,recover_after
        had_error=True;last_error=str(ex);disposition.enabled=False
        recover_after=0
        if not control.owner and not isinstance(ex,PlacementError):
            try:disposition.restore()
            except Exception as restore_error:note('Restauration partielle : '+str(restore_error))
        if isinstance(ex,PlacementError) and disposition.p and not closing and recovery_attempts<3 and all(disposition.api.valid(pid,e) for pid,e in disposition.p.items()):
            recover_after=time.monotonic()+.5*(2**recovery_attempts)
            hint.set('Un redimensionnement a pris du retard. Nouvelle tentative automatique…')
            note('Position à rétablir — reprise automatique prévue : '+last_error)
        else:
            hint.set(last_error+' Clique sur « Relancer la détection » après correction.')
            note('Interrompu : '+last_error)
        refresh()

    def recover_geometry():
        nonlocal recover_after,recovery_attempts,had_error,last_error
        recover_after=0;recovery_attempts+=1
        try:
            disposition.restore();disposition.enabled=desired_enabled
            if desired_enabled and combat and recovery_target in disposition.p:disposition.turn(recovery_target,True)
            had_error=False;last_error='';recovery_attempts=0
            hint.set('Position rétablie. Les échanges ont repris.' if desired_enabled else 'Position rétablie. La pause est conservée.')
            note('Position rétablie automatiquement — '+('échanges repris' if desired_enabled else 'pause conservée'));refresh()
        except Exception as ex:failure(ex)

    def populate(snap):
        labels.clear()
        for pid,entry in sorted(snap.items(),key=lambda item:item[0]!=disposition.main):labels[entry['name']]=pid
        combo.configure(values=list(labels))
        choice.set(snap[disposition.main]['name'])

    def memorize():
        if control.owner or closing or restarting:return
        try:
            resume=disposition.enabled
            if resume:disposition.pause()
            snap=disposition.remember(labels.get(choice.get()))
            populate(snap);disposition.enabled=resume
            hint.set('Les emplacements actuels deviennent la nouvelle position P.')
            note('P mémorisée',principal=disposition.main,fenetres=snap);refresh()
        except Exception as ex:failure(ex)

    def pause():
        nonlocal desired_enabled
        if control.owner or closing or restarting or had_error or not ready:return
        try:
            if disposition.enabled:
                desired_enabled=False;disposition.pause();note('Échanges suspendus — P restaurée')
            else:
                disposition.enabled=True;desired_enabled=True;note('Échanges activés')
            refresh()
        except Exception as ex:failure(ex)

    def restore():
        nonlocal desired_enabled
        if control.owner or closing or restarting:return
        try:desired_enabled=False;disposition.pause();note('P restaurée — échanges en pause');refresh()
        except Exception as ex:failure(ex)

    def start_detection():
        nonlocal q,stop,thread,ready,had_error,last_error,restarting,combat,recover_after,recovery_attempts,recovery_target
        q=queue.Queue();stop=threading.Event();thread=None;ready=False;combat=False;had_error=False;last_error=''
        recover_after=0;recovery_attempts=0;recovery_target=None
        turn.set('Tour : en attente');activity.set('Détection : démarrage…')
        try:
            if control.owner:
                snap=disposition.p
            elif control.recover_manual():
                snap=disposition.p;note('Échange manuel retrouvé — attente du retour à P')
            else:
                snap=disposition.api.snapshot()
                if len(snap)!=4:raise RuntimeError('Il faut quatre fenêtres WAKFU ouvertes.')
                if disposition.p and set(snap)==set(disposition.p) and all(disposition.api.valid(pid,e) for pid,e in disposition.p.items()):
                    disposition.restore()
                    for pid,entry in snap.items():disposition.p[pid]['name']=entry['name']
                    snap=disposition.p
                else:
                    selected=labels.get(choice.get())
                    disposition.p={};disposition.main=disposition.current=None
                    try:snap=disposition.remember(selected)
                    except Exception as original:
                        try:principal=disposition.recover_saved();snap=disposition.remember(principal)
                        except Exception:raise original
                    disposition.restore()
                disposition.enabled=desired_enabled
            populate(snap)
            note('Position P prête',principal=disposition.main,fenetres=snap)
            thread=threading.Thread(target=capture_worker,args=(q,stop,True),daemon=False);thread.start()
            hint.set('Les échanges se font uniquement pendant un combat confirmé.' if not control.owner else 'Utilise Retour à P dans Wakfu commandes pour reprendre.')
        except Exception as ex:failure(ex)
        restarting=False;refresh()

    def restart():
        nonlocal restarting,ready,recover_after,recovery_attempts
        if closing or restarting or control.owner:return
        restarting=True;ready=False;disposition.enabled=False;stop.set();recover_after=0;recovery_attempts=0
        try:disposition.restore()
        except Exception as ex:note('Préparation de la relance : '+str(ex))
        hint.set('La détection précédente se termine, puis les quatre fenêtres seront retrouvées.')
        note('Relance de la détection demandée');refresh()

    pausebutton=ttk.Button(buttons,text='Suspendre',command=pause);pausebutton.pack(side='left')
    restorebutton=ttk.Button(buttons,text='Restaurer P',command=restore);restorebutton.pack(side='left',padx=8)
    memorizebutton=ttk.Button(buttons,text='Mémoriser P',command=memorize);memorizebutton.pack(side='left',padx=0)
    restartbutton=ttk.Button(buttons,text='Relancer la détection',command=restart);restartbutton.pack(side='right')

    def close():
        nonlocal closing,ready
        if closing:return
        closing=True;ready=False;disposition.enabled=False;stop.set()
        try:
            if not control.owner:disposition.restore()
        except Exception as ex:note('Restauration partielle à la fermeture : '+str(ex))
        note('Fermeture demandée');refresh()
    root.protocol('WM_DELETE_WINDOW',close)

    def callback_error(kind,value,tb):
        with (folder/'erreurs.log').open('a',encoding='utf-8') as errors:errors.write(''.join(traceback.format_exception(kind,value,tb)))
        try:failure(value)
        except Exception:stop.set()
    root.report_callback_exception=callback_error

    def update():
        nonlocal ready,combat,last_check,last_publish,desired_enabled,recovery_target,recover_after
        destroyed=False
        try:
            for action,result in control.poll(allow_resume=not had_error and not closing and not restarting):
                if result['ok']:
                    if action=='reserve':recover_after=0
                    if action=='release' and not had_error:desired_enabled=disposition.enabled
                    note('Échange manuel — automatique suspendu' if action=='reserve' else 'Retour à P manuel — '+('automatique repris' if disposition.enabled else 'automatique en pause'))
                    hint.set('Utilise Retour à P dans Wakfu commandes pour reprendre.' if control.owner else 'Les échanges se font uniquement pendant un combat confirmé.')
                else:note('Demande manuelle interrompue : '+result['message'])
                refresh()
            while True:
                try:e=q.get_nowait()
                except queue.Empty:break
                kind=e['type']
                if kind=='ready':
                    ready=True;activity.set('Détection active — '+time.strftime('%H:%M:%S'));note('Détection audio et journaux actifs');refresh()
                elif kind=='combat':
                    combat=e['actif']
                    if not combat:
                        recovery_target=None
                        if not control.owner:disposition.finish()
                        turn.set('Tour : aucun');note('Hors combat — échange manuel conservé' if control.owner else 'Hors combat — P restaurée')
                    else:note('Combat détecté : '+', '.join(e['combats']))
                    refresh()
                elif kind=='tour':
                    recovery_target=e['pid']
                    turn.set('Tour de : '+e['instance'])
                    if not had_error and not restarting and combat and e['combat_confirme'] and disposition.enabled and e.get('monotonic',0)>=control.resumed_at:
                        focused=disposition.turn(e['pid'],True)
                        note('Tour de '+e['instance']+(' — disposition P' if e['pid']==disposition.main else ' — place principale'),pid=e['pid'],similarite=e['similarite'])
                        if focused is False:hint.set('Windows a refusé le focus : clique sur la fenêtre affichée.');note('Focus refusé par Windows')
                elif kind=='error':
                    failure(e['message']);stop.set()
                elif kind=='heartbeat':
                    activity.set('Détection active — vérifiée à '+time.strftime('%H:%M:%S'))
                    if e.get('audio'):
                        descriptions=[item['nom']+(' : son' if item['pic_db']>-70 else ' : silence') for item in e['audio'].values()]
                        audio_state.set('Son — '+' · '.join(descriptions))
                elif kind=='stopped':
                    ready=False;disposition.enabled=False;activity.set('Détection arrêtée')
                    if not closing and not restarting and not had_error:failure('La détection s’est arrêtée.')
                    note('Détection arrêtée');refresh()
            if closing and (thread is None or not thread.is_alive()):
                control.close();audit.close();root.destroy();destroyed=True;return
            if restarting and (thread is None or not thread.is_alive()):start_detection()
            if recover_after and time.monotonic()>=recover_after and not closing and not restarting and not control.owner:recover_geometry()
            if ready and disposition.enabled and not had_error and not restarting and (combat or disposition.current not in (None,disposition.main)) and time.monotonic()-last_check>.5:
                last_check=time.monotonic()
                for correction in disposition.check():note('Emplacement corrigé : '+correction['name'],**correction)
            if time.monotonic()-last_publish>=1:
                last_publish=time.monotonic();refresh()
        except Exception as ex:failure(ex)
        finally:
            if not destroyed:root.after(80,update)

    try:
        start_detection()
        if test_hook:
            test_hook(root,{'restart':restart,'pause':pause,'close':close},lambda:{'ready':ready,'error':had_error,'issue':last_error,'status':status.get(),'enabled':disposition.enabled,'thread':thread,'history':history,'buttons':buttons})
        root.after(80,update);root.mainloop()
    finally:
        stop.set()
        if thread is not None:thread.join(5)
        control.close()
        if not audit.closed:audit.close()
        KERNEL.CloseHandle(mutex)

if __name__=='__main__':
    try:main()
    except Exception:
        (ROOT/'switcheur').mkdir(parents=True,exist_ok=True)
        (ROOT/'switcheur'/'erreur-demarrage.log').write_text(traceback.format_exc(),encoding='utf-8')
        raise
