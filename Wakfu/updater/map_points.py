"""Read downloaded map POI records using official act/acr/acs/acq serialization."""
import pathlib,struct,zipfile
class Plain:
    def __init__(self,b):self.b=b;self.p=0;self.bit_position=-1;self.bit_index=-1;self.bit_value=0
    def read(self,fmt):
        size=struct.calcsize('<'+fmt);v=struct.unpack_from('<'+fmt,self.b,self.p)[0];self.p+=size;return v
    def string(self):
        end=self.b.index(b'\0',self.p);v=self.b[self.p:end].decode('utf8');self.p=end+1;return v
    def boolean(self):
        # aoG.bGa() packs consecutive booleans into a byte.
        if self.p==self.bit_position and self.bit_index<=6:self.bit_index+=1
        else:self.bit_value=self.read('B');self.bit_index=0;self.bit_position=self.p
        return bool(self.bit_value&(1<<self.bit_index))
def points(root):
    rows=[];interactive=[]
    with zipfile.ZipFile(pathlib.Path(root)/'contents/maps/data.jar') as z:
        for name in z.namelist():
            if not name.startswith('poi/') or not name.endswith('/map.poi'):continue
            world_id=int(name.split('/')[1]);r=Plain(z.read(name));version=r.read('b')
            if version!=0:raise ValueError('Unsupported POI version')
            for _ in range(r.read('H')):
                fields=['id','x','y','z','type','subtype','achievement_goal_id','version_major','version_minor','link_kind','link_id','linked_world_id']
                formats=['i','i','i','h','b','b','i','h','h','b','i','h']
                row={'world_id':world_id,**{k:r.read(f) for k,f in zip(fields,formats)}}
                row['descriptions']=[{'id':r.read('i'),'icon_id':r.read('h'),'criterion':r.string()} for _ in range(r.read('b'))]
                rows.append(row)
            for _ in range(r.read('h')):
                row={'world_id':world_id,'id':r.read('q'),'type':r.read('h')}
                row['parameters']=[r.read('i') for _ in range(r.read('B'))]
                n=r.read('H');row['payload_hex']=r.b[r.p:r.p+n].hex();r.p+=n
                row['flag']=r.boolean();row['icon_id']=r.read('h');interactive.append(row)
            if r.p!=len(r.b):raise ValueError(f'POI trailing bytes {name}: {len(r.b)-r.p}')
    return rows,interactive
