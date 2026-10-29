"""Regression checks for placement settling and unchanged audio recognition."""
import ast,json,time,zipfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'))
import numpy as np
import DetecteurTourWakfu as audio
import FenetresWakfu as geometry

backup=sorted((ROOT/'code').glob('sauvegarde-stabilite-*.zip'))[-1]
with zipfile.ZipFile(backup) as z:old_text=z.read('DetecteurTourWakfu.py').decode('utf-8-sig')
node=next(n for n in ast.parse(old_text).body if isinstance(n,ast.ClassDef) and n.name=='Matcher')
namespace={'np':np};exec(compile(ast.Module(body=[node],type_ignores=[]),'old-matcher','exec'),namespace)
OldMatcher=namespace['Matcher']

class AudioChecks(unittest.TestCase):
    def run_stream(self,signal,cls):
        m=cls(audio.template());events=[];position=0
        for count in [173,661,917,440]*((len(signal)//2000)+2):
            if position>=len(signal):break
            result=m.feed(signal[position:position+count]);position+=count
            if result:events.append(result)
        return events
    def test_same_detections_across_chunk_boundaries_and_gain(self):
        rng=np.random.default_rng(31);r=audio.template()
        for gain in (.1,.5,1.,2.):
            signal=rng.normal(0,.00001,19000);signal[1500:1500+len(r)]+=gain*r;signal[12500:12500+len(r)]+=gain*r
            old=self.run_stream(signal,OldMatcher);new=self.run_stream(signal,audio.Matcher)
            self.assertEqual(len(old),len(new));self.assertGreater(len(new),0)
            np.testing.assert_allclose(new,old,rtol=1e-12,atol=1e-12)
    def test_silence_and_noise_do_not_trigger(self):
        rng=np.random.default_rng(29)
        for signal in (np.zeros(20000),rng.normal(0,.000005,20000),rng.normal(0,.01,20000)):
            self.assertEqual(self.run_stream(signal,audio.Matcher),[])
    def test_fft_reference_reused(self):
        m=audio.Matcher(audio.template());rng=np.random.default_rng(2)
        for _ in range(20):m.feed(rng.normal(0,.02,660))
        self.assertLessEqual(len(m.spectra),2)

class PlacementChecks(unittest.TestCase):
    def test_delayed_window_settles_after_old_timeout(self):
        elapsed=[0.];moves=[];wanted=[0,0,1000,800]
        class Native:
            def MonitorFromRect(self,*args):return 1
            def GetMonitorInfoW(self,handle,pointer):pointer._obj.bounds=geometry.W.RECT(-5000,-5000,5000,5000);return True
            def IsZoomed(self,h):return False
            def IsIconic(self,h):return False
            def SetWindowPos(self,*args):moves.append(elapsed[0]);return True
        clock=types.SimpleNamespace(monotonic=lambda:elapsed[0],sleep=lambda seconds:elapsed.__setitem__(0,elapsed[0]+seconds))
        api=geometry.WindowsAPI();api.rectangle=lambda e:list(wanted) if elapsed[0]>=.30 else [4,4,1004,804]
        with patch.object(geometry,'USER',Native()),patch.object(geometry,'time',clock):api.place({'handle':1,'name':'Test'}, {'rect':wanted})
        self.assertGreater(elapsed[0],.16);self.assertLess(elapsed[0],.8);self.assertLessEqual(len(moves),3)
    def test_borders_tolerated_but_other_screen_rejected(self):
        self.assertTrue(geometry.same_rect([0,0,1920,1080],[0,0,1921,1081]))
        self.assertFalse(geometry.same_rect([1920,0,3840,1080],[0,0,1920,1080]))
    def test_persistent_resize_remains_a_recoverable_error(self):
        elapsed=[0.];wanted=[0,0,1000,800]
        class Native:
            def MonitorFromRect(self,*args):return 1
            def GetMonitorInfoW(self,handle,pointer):pointer._obj.bounds=geometry.W.RECT(-5000,-5000,5000,5000);return True
            def IsZoomed(self,h):return False
            def IsIconic(self,h):return False
            def SetWindowPos(self,*args):return True
        clock=types.SimpleNamespace(monotonic=lambda:elapsed[0],sleep=lambda seconds:elapsed.__setitem__(0,elapsed[0]+seconds))
        api=geometry.WindowsAPI();api.rectangle=lambda e:[20,20,1020,820]
        with patch.object(geometry,'USER',Native()),patch.object(geometry,'time',clock),self.assertRaises(geometry.PlacementError):
            api.place({'handle':1,'name':'Test'},{'rect':wanted})

def benchmark():
    rng=np.random.default_rng(8);blocks=[rng.normal(0,.01,662) for _ in range(3000)]
    reference=audio.template();report={}
    for label,data in (('son',blocks),('silence',[np.zeros(662)]*3000)):
        values={}
        for name,cls in (('avant',OldMatcher),('apres',audio.Matcher)):
            samples=[]
            for repeat in range(3):
                m=cls(reference);start=time.perf_counter()
                for block in data:m.feed(block)
                samples.append(time.perf_counter()-start)
            values[name+'_ms']=round(min(samples)/len(data)*1000,4)
        values['gain_pourcent']=round(100*(1-values['apres_ms']/values['avant_ms']),1);report[label]=values
    (ROOT/'code'/'mesures-detection.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():raise SystemExit(1)
    benchmark()
