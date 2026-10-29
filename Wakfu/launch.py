"""Portable local launcher: Python 3.10+, standard library, no machine paths."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

ROOT=Path(__file__).resolve().parent

def installation_id(root):
    return hashlib.sha256(str(root.resolve()).encode('utf-8')).hexdigest()

def status(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/initialization',timeout=1) as response:
            return json.load(response)
    except (OSError,ValueError):return None

def available_port(preferred):
    with socket.socket() as sock:
        try:sock.bind(('127.0.0.1',preferred))
        except OSError:sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]

def launch(port=8765,open_browser=True):
    if sys.version_info<(3,10):raise RuntimeError('Python 3.10 ou plus est nécessaire.')
    if not 1<=port<=65535:raise ValueError('Port invalide')
    existing=status(port)
    process=None
    if not existing or existing.get('installation_id')!=installation_id(ROOT):
        port=available_port(port)
        log=ROOT/'web/server-errors.log'
        with log.open('ab') as output:
            process=subprocess.Popen([sys.executable,'-X','utf8','-B',str(ROOT/'web/server.py'),'--port',str(port)],
                cwd=ROOT,stdout=output,stderr=output,stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        for _ in range(40):
            state=status(port)
            if state and state.get('installation_id')==installation_id(ROOT):break
            if process.poll() is not None:raise RuntimeError('Le serveur ne démarre pas. Consultez web/server-errors.log.')
            time.sleep(.25)
        else:
            process.terminate()
            raise RuntimeError('Le serveur ne répond pas. Consultez web/server-errors.log.')
    url=f'http://127.0.0.1:{port}/'
    if open_browser:webbrowser.open(url)
    print('WAKFU Atlas : '+url,flush=True)
    return url

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    try:launch(args.port,not args.no_browser)
    except (OSError,RuntimeError,ValueError) as error:
        print(str(error),file=sys.stderr);sys.exit(1)
