"""Python port of wakfu-bdata decoder; strict schema/record boundary validation."""
import json,pathlib,re,struct,zipfile
class Reader:
    def __init__(self,raw,mul):self.raw=raw;self.offset=0;self.reset(mul)
    def take(self,n):
        b=self.raw[self.offset:self.offset+n];self.offset+=n
        if len(b)!=n:raise ValueError('Unexpected end of data')
        return b
    def reset(self,mul):
        self.mul=mul;self.add=struct.unpack('<i',self.take(4))[0]+756423;self.seed=self.signed((mul^self.add)&255,8);self.pos=4
    @staticmethod
    def signed(v,bits):return ((v+(1<<(bits-1)))%(1<<bits))-(1<<(bits-1))
    def scalar(self,t):
        fmt={'i8':'b','i16':'h','i32':'i','i64':'q','bool':'b','f32':'f','f64':'d'}[t];size=struct.calcsize(fmt)
        self.seed=self.signed(self.seed+self.mul*self.pos+self.add,8);self.pos+=size
        v=struct.unpack('<'+fmt,self.take(size))[0]
        if t.startswith('f'):return v
        v=self.signed(v-self.seed,size*8)
        return bool(v) if t=='bool' else v
    def count(self):
        n=self.scalar('i32')
        if not 0<=n<=1000000:raise ValueError('Invalid collection size '+str(n))
        return n
    def read(self,t,schemas):
        if t=='String':
            n=self.count();b=self.take(n);self.pos+=n;return b.decode('utf-8')
        if t.startswith('Vec<'):return [self.read(t[4:-1],schemas) for _ in range(self.count())]
        if t.startswith('Option<'):return self.read(t[7:-1],schemas) if self.scalar('bool') else None
        if t in schemas:
            result={}
            for n,typ in schemas[t]:
                try:result[n]=self.read(typ,schemas)
                except ValueError as e:raise ValueError(f'{t}.{n} at {self.offset}: {e}') from e
            return result
        return self.scalar(t)
def schemas(directory):
    result={};types={}
    for p in pathlib.Path(directory).glob('*.rs'):
        text=p.read_text('utf8')
        for name,body in re.findall(r'pub struct (\w+)\s*\{(.*?)\n\}',text,re.S):
            result[name]=re.findall(r'pub (\w+): ([^,\n]+),',body)
        for name,ident in re.findall(r'impl BinaryData for (\w+)\s*\{\s*const TYPE_ID: i16 = (\d+);',text):types[name]=int(ident)
    return result,types
def document(path,name,defs,types):
    ident=types[name]
    with zipfile.ZipFile(path) as z:raw=z.read(str(ident)+'.bin')
    r=Reader(raw,ident)
    entries=[(r.scalar('i64'),r.scalar('i32'),r.scalar('i32'),r.scalar('i8')) for _ in range(r.count())]
    for _ in range(r.scalar('i8')):
        unique=r.scalar('bool');index_name=r.read('String',defs)
        for _ in range(r.count()):
            r.scalar('i64');r.scalar('i32') if unique else r.read('Vec<i32>',defs)
    r.reset(ident);rows=[]
    for eid,pos,size,seed in entries:
        start=r.offset;row=r.read(name,defs)
        if 'field_0' in row and row['field_0']!=eid:raise ValueError('Record ID mismatch')
        if r.offset-start!=size:raise ValueError(f'{name} record {eid}: consumed {r.offset-start}, expected {size}; row={str(row)[:700]}')
        rows.append(row)
    if r.offset!=len(raw):raise ValueError(f'{name}: trailing bytes {len(raw)-r.offset}')
    return rows
