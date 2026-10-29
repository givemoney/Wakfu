"""Official static geography; no process access or hand-written place mappings."""
import json, pathlib, sqlite3, xml.etree.ElementTree as ET, zipfile
from world_reader import worlds

def datasets(root, names):
    root=pathlib.Path(root)
    w,t=worlds(root/'contents/maps/data.jar')
    by={r['id']:r for r in w};paper={}
    with zipfile.ZipFile(root/'contents/maps/paper/full.jar') as z:
        for name in z.namelist():
            if not name.endswith('/coords.xml'):continue
            parent=int(name.split('/')[0])
            for node in ET.fromstring(z.read(name)).findall('coord'):
                if node.get('type')=='deco':continue
                ident=int(node.attrib['id']);paper.setdefault(ident,set()).add(parent)
    def region(ident):
        seen=set();current=ident
        while current in by and current not in seen:
            seen.add(current);parent=by[current]['parent_id']
            if parent<=0 or parent==current:break
            current=parent
        return current
    maps=[]
    for r in w:
        rid=region(r['id'])
        maps.append({'id':r['id'],'parent_id':r['parent_id'],'nation_id':r['nation_id'],
          'name':names.get((77,r['id'])),'region_id':rid,'region_name':names.get((77,rid)),
          'world_map_visible':int(rid in paper),'binary':r})
    territories=[{'id':r['id'],'world_id':r['world_id'],'name':names.get((66,r['id'])),
                  'cells':r['cells'],'raw_name':r['raw_name']} for r in t]
    return {'geography_worlds':maps,'geography_territories':territories}

def install_relations(db):
    db.executescript('''
    CREATE INDEX IF NOT EXISTS geography_territories_world ON geography_territories(world_id);
    DROP VIEW IF EXISTS monster_territory_hints;
    CREATE VIEW monster_territory_hints AS
      SELECT DISTINCT m.id monster_id,m.family_id,p.id protector_id,t.id territory_id,
        t.name territory_name,t.world_id,w.name world_name,w.region_id,w.region_name
      FROM client_monsters m
      JOIN source_records r ON r.dataset='client_protectors'
      JOIN client_protectors p ON p.id=json_extract(r.payload,'$.definition.id')
      JOIN json_each(r.payload,'$.definition.binary.field_14') f
        ON json_extract(f.value,'$.field_0')=m.family_id AND json_extract(f.value,'$.field_2')>0
      JOIN geography_territories t ON t.id=json_extract(r.payload,'$.definition.binary.field_7')
      JOIN geography_worlds w ON w.id=t.world_id;
    ''')

def enrich_world(db, world_id, territory_id=None):
    row=db.execute('SELECT id,name,region_id,region_name FROM geography_worlds WHERE id=?',(world_id,)).fetchone()
    if not row:return {}
    result=dict(zip(['world_id','map_name','region_id','region_name'],row))
    if territory_id is not None:
        t=db.execute('SELECT name FROM geography_territories WHERE id=? AND world_id=?',(territory_id,world_id)).fetchone()
        if t and t[0]:result['territory_name']=t[0]
    return result

def territory_at(db,world_id,x,y):
    # bMh.dV -> Vf/Ve floor coordinates /18; UL/GS packs x then y.
    cell=(((x//18)&65535)<<16)|((y//18)&65535)
    if cell>=2**31:cell-=2**32
    matches=[]
    for ident,cells in db.execute("SELECT t.id,a.value FROM geography_territories t JOIN arrays a ON a.entity='geography_territories' AND a.entity_id=t.id AND a.field='cells' WHERE t.world_id=?",(world_id,)):
        if json.loads(cells)==cell:matches.append(ident)
    return matches[0] if len(matches)==1 else None
