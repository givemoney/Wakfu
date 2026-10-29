import argparse, json, os, pathlib, tempfile, urllib.request
from download import download, BASE
from import_data import build
def update(root, reference_path=None):
    root=pathlib.Path(root).resolve(); root.mkdir(parents=True,exist_ok=True)
    lock=root/'.update.lock'
    with lock.open('x') as f: f.write(str(os.getpid()))
    try:
        reference=json.loads(pathlib.Path(reference_path).read_text('utf-8')) if reference_path else None
        if reference and (root/'wakfu.sqlite').exists():
            raise ValueError('Une base existe déjà : initialisation annulée pour la préserver.')
        with tempfile.TemporaryDirectory(prefix='.wakfu-build-',dir=root) as tmp:
            manifest=download(tmp,reference) if reference else download(tmp)
            candidate=pathlib.Path(tmp)/'wakfu.sqlite'
            report=build(tmp,candidate)
            if reference:
                from snapshot import verify
                verify(candidate,reference)
            else:
                with urllib.request.urlopen(BASE+'config.json',timeout=60) as r:
                    if json.load(r)['version']!=manifest['version']: raise RuntimeError('CDN version changed; retry')
            report_path=pathlib.Path(tmp)/'report.json'
            report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            if reference:
                # Publish only a fully verified database; never overwrite an existing one.
                os.link(candidate,root/'wakfu.sqlite')
                candidate.unlink()
            else:
                os.replace(candidate,root/'wakfu.sqlite')
            os.replace(report_path,root/'report.json')
            location_snapshot=pathlib.Path(tmp)/'harvest-locations.snapshot'
            if location_snapshot.is_file():
                os.replace(location_snapshot,root/'harvest-locations.json')
            print(json.dumps({'version':report['version'],'counts':report['counts'],'audit':report['audit'],'database_bytes':report['database_bytes']},indent=2))
    finally: lock.unlink()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default=str(pathlib.Path(__file__).resolve().parent.parent));p.add_argument('--initialize-reference');a=p.parse_args();update(a.root,a.initialize_reference)
