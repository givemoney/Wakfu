import struct, zipfile

def worlds(path):
    with zipfile.ZipFile(path) as z: b=z.read('worlds.lib')
    p=0
    def read(f):
        nonlocal p
        s=struct.calcsize('<'+f);v=struct.unpack_from('<'+f,b,p);p+=s;return v[0] if len(v)==1 else v
    def skip(n):
        nonlocal p
        if n<0 or p+n>len(b):raise ValueError('Invalid world boundary')
        p+=n
    result=[];territories=[]
    for _ in range(read('h')):
        wid,parent,nation=read('q'),read('q'),read('i');skip(8)
        skip(read('b')*15);kind=read('b');flags=list(read('10B'));access=read('b');skip(6);extra=read('h')
        for _ in range(read('B')):
            ident=read('i');size=read('H');raw=b[p:p+size];skip(size)
            cells=[read('i') for _ in range(read('i'))];levels=read('hh')
            territories.append({'id':ident,'world_id':wid,'raw_name':raw.decode('utf8'),'cells':cells,'level_a_raw':levels[0],'level_b_raw':levels[1]})
        for _ in range(read('B')):
            skip(6)
            for _ in range(2):
                skip(4);skip(read('B')*12)
            for _ in range(read('i')):
                skip(4)
                for _ in range(2):skip(read('i')*4)
        result.append({'id':wid,'parent_id':parent,'nation_id':nation,'kind_raw':kind,'flags':flags,'extra_raw':extra,'access_raw':access})
    if p!=len(b):raise ValueError(f'World archive trailing bytes {len(b)-p}')
    if len({r['id'] for r in territories})!=len(territories):raise ValueError('Duplicate territory id')
    return result,territories

