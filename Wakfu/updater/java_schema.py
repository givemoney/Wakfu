"""Read class metadata without executing game code. Extract current serialized fields."""
import pathlib,struct,zipfile,json
class Class:
    def __init__(self,b):
        self.b=b;self.o=8;self.cp=[None];count=self.u2()
        while len(self.cp)<count:
            tag=self.u1()
            if tag==1:v=self.take(self.u2()).decode('utf8','replace')
            elif tag in (3,4):v=self.take(4)
            elif tag in (5,6):v=self.take(8)
            elif tag in (7,8,16,19,20):v=self.u2()
            elif tag in (9,10,11,12,18,17):v=(self.u2(),self.u2())
            elif tag==15:v=(self.u1(),self.u2())
            else:raise ValueError(tag)
            self.cp.append((tag,v))
            if tag in (5,6):self.cp.append(None)
        self.access=self.u2();self.name=self.cls(self.u2());self.parent=self.cls(self.u2())
        self.interfaces=[self.cls(self.u2()) for _ in range(self.u2())]
        self.fields=self.members();self.methods=self.members()
    def take(self,n):v=self.b[self.o:self.o+n];self.o+=n;return v
    def u1(self):return self.take(1)[0]
    def u2(self):return struct.unpack('>H',self.take(2))[0]
    def u4(self):return struct.unpack('>I',self.take(4))[0]
    def text(self,i):return self.cp[i][1]
    def cls(self,i):return self.text(self.cp[i][1]) if i else None
    def ref(self,i):
        c,nt=self.cp[i][1];n,t=self.cp[nt][1];return self.cls(c),self.text(n),self.text(t)
    def attrs(self):return {self.text(self.u2()):self.take(self.u4()) for _ in range(self.u2())}
    def members(self):
        rows=[]
        for _ in range(self.u2()):
            access=self.u2();name=self.text(self.u2());desc=self.text(self.u2());a=self.attrs();rows.append((access,name,desc,a))
        return rows
    def code(self,m):
        b=m[3].get('Code');return b[8:8+struct.unpack('>I',b[4:8])[0]] if b else b''
def current_schemas(root):
    with zipfile.ZipFile(pathlib.Path(root)/'lib/wakfu-client.jar') as z:
        classes={n[:-6]:Class(z.read(n)) for n in z.namelist() if n.endswith('.class')}
    enum=None
    for c in classes.values():
        literals={c.text(v[1]) for v in c.cp if v and v[0]==8}
        if {'MONSTER','MONSTER_TYPE','LOOT_LIST'}.issubset(literals):enum=c;break
    if enum is None:raise ValueError('Binary type enum not found')
    code=enum.code(next(m for m in enum.methods if m[1]=='<clinit>'));i=0;values={}
    def integer():
        nonlocal i
        op=code[i];i+=1
        if 2<=op<=8:return op-3
        if op==16:v=struct.unpack('>b',code[i:i+1])[0];i+=1;return v
        if op==17:v=struct.unpack('>h',code[i:i+2])[0];i+=2;return v
        raise ValueError('Unexpected enum integer '+str(op))
    while i<len(code) and code[i]==187:
        i+=3;assert code[i]==89;i+=1
        op=code[i];i+=1
        if op==18:index=code[i];i+=1
        elif op==19:index=struct.unpack('>H',code[i:i+2])[0];i+=2
        else:raise ValueError(op)
        title=enum.text(enum.cp[index][1]);ordinal=integer();ident=integer()
        assert code[i]==183;i+=3;assert code[i]==179
        ref=struct.unpack('>H',code[i+1:i+3])[0];i+=3
        field=enum.ref(ref)[1];values[field]=(title,ident)
    mapped={};defs={};mapping={}
    def typ(desc):
        if desc.startswith('['):return 'Vec<'+typ(desc[1:])+'>'
        if desc.startswith('L'):
            name=desc[1:-1]
            if name=='java/lang/String':return 'String'
            if name not in classes:raise ValueError('Unsupported class '+name)
            build(name);return name
        return {'I':'i32','S':'i16','B':'i8','J':'i64','Z':'bool','F':'f32','D':'f64','C':'i16'}[desc]
    def build(name):
        if name in defs:return
        defs[name]=[]
        defs[name]=[('field_'+str(i),typ(f[2])) for i,f in enumerate(classes[name].fields) if f[0]&4]
    for c in classes.values():
        for m in c.methods:
            if m[2]!='()I' or not m[0]&16:continue
            b=c.code(m)
            if len(b)<3 or b[0]!=178:continue
            owner,field,_=c.ref(struct.unpack('>H',b[1:3])[0])
            if owner!=enum.name or field not in values:continue
            name,ident=values[field]
            try:build(c.name)
            except (KeyError,ValueError):continue
            if not defs[c.name]:continue
            # Legacy numbered archives use the a* classes; f* classes serve the newer bdat system.
            if name not in mapped or c.name.startswith('a'):
                mapped[name]=ident;mapping[name]=c.name
    # Retain exact field order and anonymous labels rather than guessing removed/added fields.
    return defs,mapped,mapping,classes
