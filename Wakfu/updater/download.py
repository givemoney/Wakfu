import concurrent.futures, hashlib, json, pathlib, urllib.request, urllib.error, time
BASE = 'https://wakfu.cdn.ankama.com/gamedata/'
FILES = 'actions collectibleResources equipmentItemTypes harvestLoots itemProperties items jobsItems recipeCategories recipeIngredients recipeResults recipes resourceTypes resources states recipePattern'.split()
PROBES = 'monsters monsterDrops drops zones areas jobs itemSources lootTables npcs achievements quests'.split()
def fetch(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as r: return r.read()
        except urllib.error.HTTPError: raise
        except OSError:
            if attempt == 2: raise
            time.sleep(attempt+1)
def download(directory, reference=None):
    directory = pathlib.Path(directory); directory.mkdir(parents=True, exist_ok=True)
    config = reference['manifest'] if reference else json.loads(fetch(BASE+'config.json')); version = config['version']
    manifest = {'version':version, 'config_url':BASE+'config.json', 'files':{}, 'probes':{}}
    def one(name):
        url = BASE+version+'/'+name+'.json'
        try:
            raw=fetch(url); data=json.loads(raw)
            if not isinstance(data,list): raise ValueError('Expected array: '+name)
            (directory/(name+'.json')).write_bytes(raw)
            return name, {'url':url,'status':200,'count':len(data),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        except urllib.error.HTTPError as e: return name, {'url':url,'status':e.code}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for name, result in pool.map(one,FILES+PROBES):
            manifest['files' if name in FILES else 'probes'][name]=result
    for name in FILES:
        if name == 'recipePattern' and manifest['files'][name]['status'] in (400,403,404): continue
        if manifest['files'][name]['status'] != 200: raise RuntimeError('Required dataset missing: '+name)
    if not reference and json.loads(fetch(BASE+'config.json'))['version'] != version: raise RuntimeError('Version changed during download; retry')
    from client_export import export
    if reference:
        for name, expected in reference['manifest']['files'].items():
            actual=manifest['files'].get(name,{})
            if any(actual.get(key)!=expected.get(key) for key in ('status','sha256','count','bytes')):
                raise ValueError('Source de référence indisponible ou modifiée : '+name)
        from cytrus import published, download_selected
        from client_export import FILES as CLIENT_FILES
        import tempfile
        expected=reference['manifest']['client_export']
        release=published(expected['build'])
        if release[4]!=expected['manifest_sha256']:
            raise ValueError('Le manifeste client ne correspond plus à la référence')
        with tempfile.TemporaryDirectory(prefix='.official-files-',dir=directory) as tmp:
            meta=download_selected(tmp,CLIENT_FILES,release)
            if meta['files']!=expected['files']:
                raise ValueError('Les archives client diffèrent de la référence')
            manifest['client_export']=export(directory,version,tmp,meta)
    else:
        manifest['client_export']=export(directory,version)
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest
if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser(); p.add_argument('directory'); a=p.parse_args()
    print(json.dumps(download(a.directory),indent=2))
