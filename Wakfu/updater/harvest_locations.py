"""Static ecosystem resource references in the official worlds.lib archive."""
import struct
import zipfile

def references(archive):
    with zipfile.ZipFile(archive) as source:
        raw=source.read('worlds.lib')
    position=0
    def read(fmt):
        nonlocal position
        size=struct.calcsize('<'+fmt)
        if position+size>len(raw):raise ValueError('Truncated world archive')
        values=struct.unpack_from('<'+fmt,raw,position);position+=size
        return values[0] if len(values)==1 else values
    def skip(count):
        nonlocal position
        if count<0 or position+count>len(raw):raise ValueError('Invalid world boundary')
        position+=count
    def count(fmt):
        value=read(fmt)
        if not 0<=value<=1000000:raise ValueError('Invalid world collection size')
        return value
    links=set()
    for _ in range(count('h')):
        world=read('q');read('q');read('i');skip(8)
        skip(count('b')*15);read('b');read('10B');read('b');skip(6);read('h')
        territories=set()
        for _ in range(count('B')):
            territories.add(read('i'));skip(count('H'));skip(count('i')*4);read('hh')
        for _ in range(count('B')):
            territory=read('i');read('BB')
            if territory not in territories:raise ValueError('Unknown ecosystem territory')
            for _ in range(2):
                skip(4);skip(count('B')*12)
            for _ in range(count('i')):
                read('i')
                for _ in range(count('i')):
                    resource=read('i')
                    links.add((territory,world,resource))
                skip(count('i')*4)
    if position!=len(raw):raise ValueError('Trailing world archive data')
    return [{'territory_id':t,'world_id':w,'resource_id':r} for t,w,r in sorted(links)]
