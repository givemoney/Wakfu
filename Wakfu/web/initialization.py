"""One local installation job, with progress available after a page reload."""
import json
import hashlib
import os
import subprocess
import sys
import threading

class Initialization:
    def __init__(self, root):
        self.root=root
        self.lock=threading.Lock()
        self.state={'state':'idle','message':'Prêt à installer les données WAKFU.'}
        self.reference=json.loads((root/'updater/reference.json').read_text('utf-8'))

    def status(self):
        with self.lock:
            value=dict(self.state)
        if (self.root/'wakfu.sqlite').is_file() and value['state']!='running':
            value={'state':'ready','message':'La base WAKFU est disponible.'}
        value['version']=self.reference['manifest']['version']
        value['installation_id']=hashlib.sha256(str(self.root.resolve()).encode('utf-8')).hexdigest()
        return value

    def start(self):
        with self.lock:
            if (self.root/'wakfu.sqlite').exists():
                raise ValueError('La base existe déjà et sera conservée.')
            if self.state['state']=='running' or (self.root/'.update.lock').exists():
                raise ValueError('Une initialisation ou mise à jour est déjà en cours.')
            self.state={'state':'running','message':'Téléchargement officiel, reconstruction puis vérification des données…'}
            threading.Thread(target=self._run,daemon=True).start()
        return self.status()

    def _run(self):
        try:
            result=subprocess.run([sys.executable,'-B',str(self.root/'updater/update.py'),
                '--root',str(self.root),'--initialize-reference',str(self.root/'updater/reference.json')],
                capture_output=True,text=True,encoding='utf-8',errors='replace',env={**os.environ,'PYTHONUTF8':'1'})
            if result.returncode:
                raise RuntimeError((result.stderr or result.stdout or 'Échec de la reconstruction.').strip().splitlines()[-1][:500])
            state={'state':'ready','message':'Installation terminée : données vérifiées, profil personnel conservé ou vide.'}
        except Exception as error:
            state={'state':'error','message':str(error)}
        with self.lock:
            self.state=state
