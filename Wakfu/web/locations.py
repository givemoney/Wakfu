"""Five gathering categories by official ecosystem territory references."""
import json
from pathlib import Path

CATEGORIES={20:('fish','Poissons',308),7:('ores','Minerais',281),1:('wood','Bois',306),2:('crops','Récoltes paysannes',309),10:('herbs','Récoltes d’herboriste',313)}

def load_reference(db):
    manifest=json.loads(db.execute("SELECT value FROM metadata WHERE key='manifest'").fetchone()[0])
    root=Path(__file__).resolve().parents[1]
    for path in (root/'harvest-locations.json',root/'updater/harvest-locations.json'):
        if not path.is_file():continue
        data=json.loads(path.read_text('utf-8'));client=manifest['client_export']
        if data.get('version')==manifest['version'] and data.get('build')==client['build'] and data.get('sha1')==client['files']['contents/maps/data.jar']['sha1']:
            return data
    return None

def prepare(db,reference=None):
    if db.execute("SELECT 1 FROM sqlite_temp_master WHERE name='atlas_harvest_zones'").fetchone():return
    reference=load_reference(db) if reference is None else reference
    db.executescript('''
    CREATE TEMP TABLE atlas_harvest_links(territory_id INTEGER,world_id INTEGER,resource_id INTEGER,PRIMARY KEY(territory_id,world_id,resource_id));
    CREATE TEMP TABLE atlas_harvest_zones(id INTEGER PRIMARY KEY,name TEXT,category TEXT,level INTEGER,level_max INTEGER,level_basis TEXT DEFAULT 'harvest',component_count INTEGER DEFAULT 0);
    CREATE TEMP TABLE atlas_harvest_products(territory_id INTEGER,item_id INTEGER,resource_id INTEGER,harvest_level INTEGER,category_key TEXT,category_label TEXT,PRIMARY KEY(territory_id,item_id,resource_id));
    ''')
    if reference is None:return
    db.executemany('INSERT OR IGNORE INTO atlas_harvest_links VALUES(?,?,?)',((r['territory_id'],r['world_id'],r['resource_id']) for r in reference['links']))
    for resource_type,(key,label,item_type) in CATEGORIES.items():
        extra=" AND h.resourceNextIndex=0 AND NOT EXISTS (SELECT 1 FROM item_names_fr wood_name WHERE wood_name.id=a.id AND instr(fold(wood_name.name),'bouture')=1)" if resource_type==1 else ''
        db.execute('''INSERT OR REPLACE INTO atlas_harvest_products
          SELECT l.territory_id,a.id,r.id,MIN(h.skillLevelRequired),?,?
          FROM atlas_harvest_links l JOIN resources r ON r.id=l.resource_id
          JOIN geography_territories t ON t.id=l.territory_id AND t.world_id=l.world_id
          JOIN harvest_actions h ON h.resourceId=r.id
          JOIN all_items a ON a.id=h.collectItemId OR a.id IN (SELECT itemId FROM harvest_loots WHERE listId=h.collectLootListId AND itemIsLootList=0)
          WHERE r.resourceType=? AND a.type_id=?
          AND t.world_id NOT IN (SELECT CAST(value AS INTEGER) FROM arrays WHERE entity='client_dungeons' AND field='instance_ids')
          '''+extra+' GROUP BY l.territory_id,a.id,r.id',(key,label,resource_type,item_type))
    db.execute('''INSERT INTO atlas_harvest_zones(id,name,category,level,level_max,component_count)
      SELECT t.id,COALESCE(t.name,'Territoire #'||t.id),COALESCE(w.name,'Carte #'||t.world_id),
        MIN(p.harvest_level),MAX(p.harvest_level),COUNT(DISTINCT p.item_id)
      FROM atlas_harvest_products p JOIN geography_territories t ON t.id=p.territory_id
      LEFT JOIN geography_worlds w ON w.id=t.world_id GROUP BY t.id''')

def rows(db,sql,args=()):return [dict(row) for row in db.execute(sql,args)]

def search(db,params):
    reference=load_reference(db);prepare(db,reference)
    query=params.get('q',[''])[0].strip()
    low=int(params.get('min',['-2147483648'])[0] or -2147483648)
    high=int(params.get('max',['2147483647'])[0] or 2147483647)
    offset=max(0,int(params.get('offset',['0'])[0]))
    where=' WHERE z.level BETWEEN ? AND ?';args=[low,high]
    if query:
        where+=" AND (instr(fold(z.name||' '||z.category),fold(?))>0 OR EXISTS (SELECT 1 FROM atlas_harvest_products p JOIN item_names_fr n ON n.id=p.item_id WHERE p.territory_id=z.id AND instr(fold(n.name),fold(?))>0))"
        args.extend([query,query])
    sort={'level':'z.level,fold(z.name),z.id','level_desc':'z.level DESC,fold(z.name),z.id','name':'fold(z.name),z.id'}.get(params.get('sort',['level'])[0],'z.level,fold(z.name),z.id')
    total=db.execute('SELECT COUNT(*) FROM atlas_harvest_zones z'+where,args).fetchone()[0]
    return {'total':total,'rows':rows(db,'SELECT z.* FROM atlas_harvest_zones z'+where+' ORDER BY '+sort+' LIMIT 36 OFFSET ?',args+[offset]),'coverage_message':None if reference else 'Localisations de récolte indisponibles pour cette version. Lancez la mise à jour des données.'}

def detail(db,params):
    prepare(db);ident=int(params.get('id',['0'])[0])
    found=rows(db,'SELECT * FROM atlas_harvest_zones WHERE id=?',(ident,))
    if not found:raise ValueError('Zone de récolte introuvable')
    result=found[0];result['kind']='locations'
    result['components']=rows(db,"SELECT p.item_id id,n.name,MIN(p.harvest_level) harvest_level,p.category_key,p.category_label FROM atlas_harvest_products p LEFT JOIN (SELECT id,MAX(name) name FROM item_names_fr GROUP BY id) n ON n.id=p.item_id WHERE p.territory_id=? GROUP BY p.item_id,p.category_key,p.category_label ORDER BY p.category_key,harvest_level,fold(n.name),p.item_id",(ident,))
    return result
