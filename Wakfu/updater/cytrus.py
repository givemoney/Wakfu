"""Minimal reader for Ankama's public FlatBuffers manifest (standard library only)."""
import collections,concurrent.futures,hashlib,json,pathlib,struct,time,urllib.request,urllib.error
BASE='https://cytrus.cdn.ankama.com/'
class Flat:
    def __init__(self,b):self.b=b
    def u32(self,p):return struct.unpack_from('<I',self.b,p)[0]
    def field(self,t,index):
        v=t-struct.unpack_from('<i',self.b,t)[0];length=struct.unpack_from('<H',self.b,v)[0]
        offset=struct.unpack_from('<H',self.b,v+4+index*2)[0] if 4+index*2<length else 0
        return t+offset if offset else None
    def indirect(self,p):return p+self.u32(p)
    def vector(self,t,index):
        p=self.field(t,index)
        if p is None:return []
        p=self.indirect(p);return [self.indirect(p+4+i*4) for i in range(self.u32(p))]
    def bytes(self,t,index):
        p=self.field(t,index)
        if p is None:return b''
        p=self.indirect(p);return self.b[p+4:p+4+self.u32(p)]
    def string(self,t,index):return self.bytes(t,index).decode('utf8')
    def long(self,t,index):
        p=self.field(t,index);return struct.unpack_from('<q',self.b,p)[0] if p else 0
def manifest(raw):
    f=Flat(raw);files={};bundles={}
    def chunk(t):return {'hash':f.bytes(t,0).hex(),'size':f.long(t,1),'offset':f.long(t,2)}
    for fragment in f.vector(f.u32(0),0):
        for t in f.vector(fragment,1):
            name=f.string(t,0);files[name]={'name':name,'size':f.long(t,1),'hash':f.bytes(t,2).hex(),'chunks':[chunk(c) for c in f.vector(t,3)]}
        for t in f.vector(fragment,2):
            bundle_hash=f.bytes(t,0).hex()
            for c in f.vector(t,1):
                entry=chunk(c);bundles[entry['hash']]={**entry,'bundle_hash':bundle_hash}
    return files,bundles
def published(version=None):
    if version is None:
        with urllib.request.urlopen(BASE+'cytrus.json',timeout=60) as r:config=json.load(r)
        version=config['games']['wakfu']['platforms']['windows']['main']
    url=BASE+'wakfu/releases/main/windows/'+version+'.manifest'
    with urllib.request.urlopen(url,timeout=60) as r:raw=r.read()
    files,bundles=manifest(raw)
    return version,url,files,bundles,hashlib.sha256(raw).hexdigest()
def download_selected(directory,names,published_data=None):
    directory=pathlib.Path(directory)
    version,url,files,bundles,sha=published_data or published()
    selected={name:dict(files[name]) for name in names}
    for file in selected.values():
        if not file['chunks']:
            if file['hash'] not in bundles:raise ValueError('Missing single-file chunk '+file['name'])
            file['chunks']=[{'hash':file['hash'],'size':file['size'],'offset':0}]
    needed={c['hash'] for file in selected.values() for c in file['chunks']}
    grouped=collections.defaultdict(list)
    for h in needed:grouped[bundles[h]['bundle_hash']].append(bundles[h])
    tasks=[]
    for bundle,chunks in grouped.items():
        ordered=sorted(chunks,key=lambda c:c['offset']);ranges=[]
        for c in ordered:
            if ranges and c['offset']<=ranges[-1][1]+131072:
                ranges[-1][1]=max(ranges[-1][1],c['offset']+c['size']);ranges[-1][2].append(c)
            else:ranges.append([c['offset'],c['offset']+c['size'],[c]])
        tasks.extend((bundle,*r) for r in ranges)
    chunk_data={}
    def get(task):
        bundle,start,end,chunks=task;url=BASE+'wakfu/bundles/'+bundle[:2]+'/'+bundle
        for attempt in range(3):
            try:
                req=urllib.request.Request(url,headers={'Range':f'bytes={start}-{end-1}'})
                with urllib.request.urlopen(req,timeout=90) as r:
                    status=r.status;raw=r.read();origin=start if status==206 else 0
                result={}
                for c in chunks:
                    b=raw[c['offset']-origin:c['offset']-origin+c['size']]
                    if hashlib.sha1(b).hexdigest()!=c['hash']:raise ValueError('Chunk hash mismatch')
                    result[c['hash']]=b
                return result
            except (OSError,ValueError):
                if attempt==2:raise
                time.sleep(attempt+1)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for result in pool.map(get,tasks):chunk_data.update(result)
    for name,file in selected.items():
        if pathlib.PurePosixPath(name).is_absolute() or '..' in pathlib.PurePosixPath(name).parts:raise ValueError('Unsafe manifest path')
        raw=bytearray(file['size'])
        for c in file['chunks']:raw[c['offset']:c['offset']+c['size']]=chunk_data[c['hash']]
        if hashlib.sha1(raw).hexdigest()!=file['hash']:raise ValueError('File hash mismatch '+name)
        target=directory/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    return {'build':version,'manifest_url':url,'manifest_sha256':sha,'files':{n:{'sha1':f['hash'],'bytes':f['size']} for n,f in selected.items()}}
