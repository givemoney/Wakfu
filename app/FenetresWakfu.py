import ctypes as C
from ctypes import wintypes as W
import json,time
from pathlib import Path
from DetecteurTourWakfu import USER,KERNEL,ENUM,ROOT

class Placement(C.Structure):
    _fields_=[('length',W.UINT),('flags',W.UINT),('showCmd',W.UINT),('ptMinPosition',W.POINT),('ptMaxPosition',W.POINT),('rcNormalPosition',W.RECT)]
class Monitor(C.Structure):
    _fields_=[('size',W.DWORD),('bounds',W.RECT),('work',W.RECT),('flags',W.DWORD)]
USER.GetWindowPlacement.argtypes=[W.HWND,C.POINTER(Placement)]
USER.SetWindowPlacement.argtypes=[W.HWND,C.POINTER(Placement)]
USER.GetWindowRect.argtypes=[W.HWND,C.POINTER(W.RECT)]
USER.MonitorFromWindow.argtypes=[W.HWND,W.DWORD];USER.MonitorFromWindow.restype=W.HANDLE
USER.MonitorFromRect.argtypes=[C.POINTER(W.RECT),W.DWORD];USER.MonitorFromRect.restype=W.HANDLE
USER.MonitorFromPoint.argtypes=[W.POINT,W.DWORD];USER.MonitorFromPoint.restype=W.HANDLE
USER.GetMonitorInfoW.argtypes=[W.HANDLE,C.POINTER(Monitor)]
USER.IsWindow.argtypes=[W.HWND];USER.GetForegroundWindow.restype=W.HWND
USER.IsZoomed.argtypes=[W.HWND];USER.IsIconic.argtypes=[W.HWND]
USER.ShowWindow.argtypes=[W.HWND,C.c_int]
USER.SetWindowPos.argtypes=[W.HWND,W.HWND,C.c_int,C.c_int,C.c_int,C.c_int,W.UINT]
USER.SetForegroundWindow.argtypes=[W.HWND];USER.BringWindowToTop.argtypes=[W.HWND]
USER.AttachThreadInput.argtypes=[W.DWORD,W.DWORD,W.BOOL]
KERNEL.GetCurrentThreadId.restype=W.DWORD

def to_dict(p):
    return {'flags':p.flags,'showCmd':p.showCmd,'min':[p.ptMinPosition.x,p.ptMinPosition.y],'max':[p.ptMaxPosition.x,p.ptMaxPosition.y],'normal':[p.rcNormalPosition.left,p.rcNormalPosition.top,p.rcNormalPosition.right,p.rcNormalPosition.bottom]}
def from_dict(d):
    p=Placement();p.length=C.sizeof(p);p.flags=d['flags'];p.showCmd=d['showCmd'];p.ptMinPosition=W.POINT(*d['min']);p.ptMaxPosition=W.POINT(*d['max']);p.rcNormalPosition=W.RECT(*d['normal']);return p

class PlacementError(RuntimeError):
    """A valid window did not settle in its requested slot in time."""

def same_rect(actual,wanted,tolerance=2):
    return len(actual)==len(wanted)==4 and all(abs(a-b)<=tolerance for a,b in zip(actual,wanted))

class WindowsAPI:
    def snapshot(self):
        found={}
        def visit(h,param):
            n=USER.GetWindowTextLengthW(h);b=C.create_unicode_buffer(n+1);USER.GetWindowTextW(h,b,n+1)
            if b.value.endswith(' - WAKFU') and USER.IsWindowVisible(h):
                pid=W.DWORD();USER.GetWindowThreadProcessId(h,C.byref(pid))
                p=Placement();p.length=C.sizeof(p)
                if not USER.GetWindowPlacement(h,C.byref(p)):raise C.WinError()
                if p.showCmd==2:raise RuntimeError('Restaure toutes les fenêtres WAKFU avant de mémoriser P.')
                rect=W.RECT();USER.GetWindowRect(h,C.byref(rect))
                monitor=Monitor();monitor.size=C.sizeof(monitor);USER.GetMonitorInfoW(USER.MonitorFromWindow(h,2),C.byref(monitor))
                found[pid.value]={'handle':int(h),'name':b.value[:-8],'placement':to_dict(p),'rect':[rect.left,rect.top,rect.right,rect.bottom],'primary':bool(monitor.flags&1)}
            return True
        # Exceptions must not escape a native callback.
        errors=[]
        @ENUM
        def safe(h,param):
            try:return visit(h,param)
            except Exception as e:errors.append(str(e));return False
        USER.EnumWindows(safe,0)
        if errors:raise RuntimeError(errors[0])
        return found
    def valid(self,pid,entry):
        if not USER.IsWindow(entry['handle']):return False
        actual=W.DWORD();USER.GetWindowThreadProcessId(entry['handle'],C.byref(actual));return actual.value==pid
    def place(self,entry,slot):
        h=entry['handle'];wanted=list(slot['rect']);left,top,right,bottom=wanted
        target=W.RECT(*wanted);monitor=Monitor();monitor.size=C.sizeof(monitor)
        if not USER.GetMonitorInfoW(USER.MonitorFromRect(C.byref(target),2),C.byref(monitor)):raise C.WinError()
        b=monitor.bounds;overlap=max(0,min(right,b.right)-max(left,b.left))*max(0,min(bottom,b.bottom)-max(top,b.top))
        if right<=left or bottom<=top or overlap<(right-left)*(bottom-top)*.90:
            self.rescue(entry)
            raise RuntimeError('Un emplacement de P est hors écran. La fenêtre a été ramenée sur le principal ; mémorise une nouvelle P.')
        if same_rect(self.rectangle(entry),wanted) and not USER.IsZoomed(h) and not USER.IsIconic(h):return
        # WAKFU's own maximize handling can offset a window by a second monitor
        # origin (observed x=-7680 instead of -3840). Keep native normal state
        # and reproduce the captured visible rectangle directly in screen pixels.
        if USER.IsZoomed(h) or USER.IsIconic(h):USER.ShowWindow(h,9)
        started=time.monotonic();next_move=0;stable=0
        while time.monotonic()-started<.8:
            elapsed=time.monotonic()-started
            if elapsed>=next_move:
                if USER.IsZoomed(h) or USER.IsIconic(h):USER.ShowWindow(h,9)
                if not USER.SetWindowPos(h,None,left,top,right-left,bottom-top,0x54):raise C.WinError()
                next_move=elapsed+.25
            time.sleep(.02)
            actual=self.rectangle(entry)
            stable=stable+1 if same_rect(actual,wanted) and not USER.IsZoomed(h) and not USER.IsIconic(h) else 0
            if stable>=2:return
        raise PlacementError(entry['name']+' : position non stabilisée. Demandée='+str(wanted)+', obtenue='+str(self.rectangle(entry))+'.')
    def rescue(self,entry):
        m=Monitor();m.size=C.sizeof(m)
        if not USER.GetMonitorInfoW(USER.MonitorFromPoint(W.POINT(0,0),1),C.byref(m)):raise C.WinError()
        r=m.work;w=min(1213,r.right-r.left-40);h=min(939,r.bottom-r.top-40)
        USER.ShowWindow(entry['handle'],9)
        if not USER.SetWindowPos(entry['handle'],None,r.left+20,r.top+20,w,h,0x54):raise C.WinError()
    def rectangle(self,entry):
        r=W.RECT()
        if not USER.GetWindowRect(entry['handle'],C.byref(r)):raise C.WinError()
        return [r.left,r.top,r.right,r.bottom]
    def focus(self,entry):
        target=entry['handle'];current=KERNEL.GetCurrentThreadId();attached=[]
        foreground=USER.GetForegroundWindow();threads=[USER.GetWindowThreadProcessId(foreground,None),USER.GetWindowThreadProcessId(target,None)]
        try:
            for t in set(threads):
                if t and t!=current and USER.AttachThreadInput(current,t,True):attached.append(t)
            USER.BringWindowToTop(target);USER.SetForegroundWindow(target)
        finally:
            for t in reversed(attached):USER.AttachThreadInput(current,t,False)
        return USER.GetForegroundWindow()==target

class Disposition:
    def __init__(self,api=None):
        self.api=api or WindowsAPI();self.p={};self.main=None;self.current=None;self.enabled=False
    def remember(self,main=None):
        if self.current is not None and self.current!=self.main:raise RuntimeError('Restaure P avant de la mémoriser à nouveau.')
        snapshot=self.api.snapshot()
        if len(snapshot)!=4:raise RuntimeError('Il faut quatre fenêtres WAKFU ouvertes pour mémoriser P.')
        candidates=[pid for pid,e in snapshot.items() if e['primary']]
        main=main if main in snapshot else (candidates[0] if len(candidates)==1 else None)
        if main is None:raise RuntimeError('Choisis le compte principal dans la liste, puis mémorise P.')
        if not snapshot[main]['primary']:raise RuntimeError('Place le compte principal sur ton écran principal, puis mémorise P.')
        self.p=snapshot;self.main=main;self.current=main
        (ROOT/'disposition-P.json').write_text(json.dumps({'principal':main,'fenetres':snapshot},ensure_ascii=False,indent=2),encoding='utf-8')
        return snapshot
    def recover_saved(self):
        data=json.loads((ROOT/'disposition-P.json').read_text(encoding='utf-8'))
        saved={int(pid):entry for pid,entry in data['fenetres'].items()};main=int(data['principal'])
        if len(saved)!=4 or main not in saved or not all(self.api.valid(pid,e) for pid,e in saved.items()):raise RuntimeError('La P enregistrée ne correspond plus aux fenêtres ouvertes.')
        current=self.api.snapshot()
        if set(current)!=set(saved):raise RuntimeError('Les instances ont changé depuis la mémorisation de P.')
        self.p=saved;self.main=main;self.current=None;self.restore()
        return main
    def restore(self,focus=False):
        if not self.p:return
        errors=[]
        for pid,e in self.p.items():
            if self.api.valid(pid,e):
                try:self.api.place(e,e)
                except Exception as ex:errors.append(ex)
            else:errors.append(RuntimeError('Une fenêtre mémorisée est fermée.'))
        self.current=self.main
        if focus and self.api.valid(self.main,self.p[self.main]):self.api.focus(self.p[self.main])
        if errors:raise (PlacementError if all(isinstance(e,PlacementError) for e in errors) else RuntimeError)('; '.join(map(str,errors)))
    def turn(self,pid,combat):
        if not self.enabled or not combat or pid not in self.p:return None
        for key,e in self.p.items():
            if not self.api.valid(key,e):self.enabled=False;self.restore();raise RuntimeError('Une fenêtre a changé. Mémorise P à nouveau.')
        if pid==self.current:return self.api.focus(self.p[pid])
        # Always derive both slots from P, never from an already swapped layout.
        try:
            if self.current!=self.main:self.api.place(self.p[self.current],self.p[self.current])
            if pid==self.main:
                self.api.place(self.p[self.main],self.p[self.main])
            else:
                self.api.place(self.p[self.main],self.p[pid])
                self.api.place(self.p[pid],self.p[self.main])
            self.current=pid
            return self.api.focus(self.p[pid])
        except Exception:
            self.enabled=False;self.restore();raise
    def finish(self):
        if self.current is not None and self.current!=self.main:self.restore(focus=True)
    def pause(self):self.enabled=False;self.restore(focus=True)
    def check(self):
        if not self.enabled:return []
        corrected=[]
        for pid,entry in self.p.items():
            if not self.api.valid(pid,entry):raise RuntimeError('Une fenêtre a été fermée. Les échanges sont suspendus.')
            slot=self.p[self.current] if pid==self.main and self.current!=self.main else self.p[self.main] if pid==self.current and pid!=self.main else entry
            actual=self.api.rectangle(entry);zoomed=bool(USER.IsZoomed(entry['handle']))
            if not same_rect(actual,slot['rect']) or zoomed:
                self.api.place(entry,slot)
                corrected.append({'pid':pid,'name':entry['name'],'avant':actual,'apres':slot['rect'],'maximisee':zoomed})
        return corrected

def selftest():
    class Fake:
        def __init__(self):self.positions={i:i for i in range(4)};self.calls=[]
        def snapshot(self):return {i:{'name':str(i),'primary':i==0,'placement':i,'handle':i} for i in range(4)}
        def valid(self,pid,e):return True
        def place(self,e,p):self.positions[e['handle']]=p['placement'];self.calls.append((e['handle'],p['placement']))
        def focus(self,e):return True
    a=Fake();d=Disposition(a);d.p=a.snapshot();d.main=d.current=0;d.enabled=True
    d.turn(1,False);assert a.positions=={i:i for i in range(4)}
    d.turn(1,True);assert a.positions=={0:1,1:0,2:2,3:3}
    n=len(a.calls);d.turn(1,True);assert len(a.calls)==n
    d.turn(2,True);assert a.positions=={0:2,1:1,2:0,3:3}
    d.turn(0,True);assert a.positions=={i:i for i in range(4)}
    d.turn(3,True);d.finish();assert a.positions=={i:i for i in range(4)}
    d.turn(1,True);d.pause();d.turn(2,True);assert a.positions=={i:i for i in range(4)}
    print('OK : échanges depuis P, retour principal, fin de combat, pause et absence de déplacement hors combat.')

if __name__=='__main__':selftest()
