"""Local, read-only WAKFU browser. Python standard library only."""
from contextlib import closing
import argparse
from cart import calculate_cart
from recipe_filter import allowed_recipes
import json
import sqlite3
import unicodedata
import threading
import ipaddress
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parents[1]
WEB = Path(__file__).resolve().parent
import sys
sys.path.insert(0,str(ROOT/'updater'))
from geography import enrich_world, territory_at
from initialization import Initialization
import locations
import dungeons
from item_stats import formatted_effects
INITIALIZATION = Initialization(ROOT)
PERSONAL = ROOT/'personal.sqlite'
def initialize_personal():
    with closing(sqlite3.connect(PERSONAL)) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS item_preferences(item_id INTEGER PRIMARY KEY,note TEXT NOT NULL DEFAULT '',favorite INTEGER NOT NULL DEFAULT 0 CHECK(favorite IN (0,1)))")
        if 'learned' not in {r[1] for r in db.execute('PRAGMA table_info(item_preferences)')}:
            db.execute('ALTER TABLE item_preferences ADD COLUMN learned INTEGER NOT NULL DEFAULT 0 CHECK(learned IN (0,1))')

def save_preference(data):
    ident=data.get('item_id')
    if type(ident) is not int or ident<=0: raise ValueError('Objet invalide')
    with closing(sqlite3.connect((ROOT/'wakfu.sqlite').as_uri()+'?mode=ro',uri=True)) as game:
        if not game.execute('SELECT 1 FROM all_items WHERE id=?',(ident,)).fetchone(): raise ValueError('Objet introuvable')
    if 'note' in data and (not isinstance(data['note'],str) or len(data['note'])>5000): raise ValueError('La note est limitée à 5 000 caractères')
    if 'favorite' in data and type(data['favorite']) is not bool: raise ValueError('Favori invalide')
    if 'learned' in data:
        if type(data['learned']) is not bool: raise ValueError('Statut appris invalide')
        with closing(sqlite3.connect((ROOT/'wakfu.sqlite').as_uri()+'?mode=ro',uri=True)) as game:
            row=game.execute('SELECT learn_furniture FROM item_learning WHERE id=?',(ident,)).fetchone()
            if not row or not row[0]: raise ValueError('Cet objet ne possède pas d’action d’apprentissage du mobilier')
    with closing(sqlite3.connect(PERSONAL)) as db, db:
        db.execute('INSERT OR IGNORE INTO item_preferences(item_id) VALUES(?)',(ident,))
        if 'note' in data: db.execute('UPDATE item_preferences SET note=? WHERE item_id=?',(data['note'],ident))
        if 'favorite' in data: db.execute('UPDATE item_preferences SET favorite=? WHERE item_id=?',(int(data['favorite']),ident))
        if 'learned' in data: db.execute('UPDATE item_preferences SET learned=? WHERE item_id=?',(int(data['learned']),ident))
        row=db.execute('SELECT note,favorite,learned FROM item_preferences WHERE item_id=?',(ident,)).fetchone()
    return {'item_id':ident,'note':row[0],'favorite':bool(row[1]),'learned':bool(row[2])}

def personal_fields(db,ident):
    row=db.execute('SELECT note,favorite,learned FROM personal.item_preferences WHERE item_id=?',(ident,)).fetchone()
    learning=db.execute('SELECT learn_furniture FROM item_learning WHERE id=?',(ident,)).fetchone()
    return {'item_id':ident,'note':row[0] if row else '', 'favorite':bool(row[1]) if row else False,'learned':bool(row[2]) if row else False,'learnable':bool(learning[0]) if learning else None}
NAMES = "WITH names AS (SELECT id, MAX(name) name FROM item_names_fr GROUP BY id) "
def prepare_catalog(db):
    db.execute('ATTACH DATABASE ? AS personal',(PERSONAL.as_uri()+'?mode=ro',))
    # Classification uses explicit source relations, never a guess from a creature name.
    db.executescript("""
    CREATE TEMP VIEW npc_family_ids AS
      WITH RECURSIVE clan(id) AS (
        SELECT entity_id FROM translations WHERE entity='monster_families'
          AND language='fr' AND field='title' AND text='Membres de clan'
        UNION SELECT f.id FROM monster_families f JOIN clan c ON f.parent_id=c.id
      ) SELECT id FROM clan;
    CREATE TEMP VIEW ui_npcs AS
      SELECT -p.id id,p.id record_id,'client_protectors' record_entity,
        NULL monster_id,t.text name,'Membre de clan · fiche de localisation' category,NULL level
      FROM client_protectors p LEFT JOIN translations t ON t.entity='client_protectors'
        AND t.entity_id=p.id AND t.language='fr' AND t.field='title'
      UNION ALL
      SELECT m.id,m.id,'client_monsters',m.id,t.text,'Membre de clan · définition de créature',NULL
      FROM client_monsters m LEFT JOIN translations t ON t.entity='client_monsters'
        AND t.entity_id=m.id AND t.language='fr' AND t.field='title'
      WHERE m.family_id IN (SELECT id FROM npc_family_ids);
    CREATE TEMP VIEW combat_creature_ids AS
      SELECT monster_id id FROM monster_drops UNION SELECT monster_id FROM dungeon_monsters;
    CREATE TEMP VIEW ui_monsters AS SELECT * FROM client_monsters
      WHERE id IN (SELECT id FROM combat_creature_ids)
        AND family_id NOT IN (SELECT id FROM npc_family_ids);
    CREATE TEMP VIEW ui_unclassified AS SELECT * FROM client_monsters
      WHERE id NOT IN (SELECT id FROM combat_creature_ids)
        AND family_id NOT IN (SELECT id FROM npc_family_ids);
    """)

def creature_kind(db, ident):
    if db.execute('SELECT 1 FROM ui_npcs WHERE monster_id=?',(ident,)).fetchone(): return 'npcs'
    if db.execute('SELECT 1 FROM ui_monsters WHERE id=?',(ident,)).fetchone(): return 'monsters'
    return 'creatures'
def fold(value):
    return ''.join(x for x in unicodedata.normalize('NFD', str(value or '').casefold()) if not unicodedata.combining(x))
def rows(db, sql, args=()):
    return [dict(r) for r in db.execute(sql, args)]
def title(db, entity, ident):
    r = db.execute("SELECT text FROM translations WHERE entity=? AND entity_id=? AND field='title' AND language='fr' LIMIT 1", (entity,ident)).fetchone()
    return r[0] if r else None
def item_name(db, ident):
    r=db.execute('SELECT name FROM item_names_fr WHERE id=? ORDER BY entity LIMIT 1',(ident,)).fetchone()
    return r[0] if r else None
def image_url(db, kind, ident):
    if kind=='npcs':
        return image_url(db,'monsters',ident) if ident>0 else None
    if kind=='creatures': kind='monsters'
    if kind=='recipes':
        r=db.execute('SELECT productedItemId FROM recipe_results WHERE recipeId=? ORDER BY productOrder LIMIT 1',(ident,)).fetchone()
        return image_url(db,'items',r[0]) if r else None
    lookup={'items':('all_items','gfx_id','item/64'),'monsters':('client_monsters','gfx_id','monster/200'),'resources':('resources','iconGfxId','item/64')}
    if kind not in lookup: return None
    table,field,folder=lookup[kind]
    r=db.execute(f'SELECT {field} FROM {table} WHERE id=?',(ident,)).fetchone()
    return f'https://static.ankama.com/wakfu/portal/game/{folder}/{int(r[0])}.png' if r and r[0] and r[0]>0 else None
def item_links(db,sql,ident):
    data=rows(db,sql,(ident,))
    for r in data: r['name']=item_name(db,r['id'])
    return data

def creature_places(db, ident):
    places=rows(db,"SELECT DISTINCT l.*,t.text entrance_world_name FROM monster_dungeon_locations l LEFT JOIN translations t ON t.entity='world_instances' AND t.entity_id=l.entrance_world_id AND t.field='title' AND t.language='fr' WHERE l.monster_id=?",(ident,))
    for place in places:
        world=place.get('associated_world_id')
        territory=territory_at(db,world,place['entrance_x'],place['entrance_y']) if place.get('entrance_x') is not None else None
        place.update(enrich_world(db,world,territory))
        place.update(relation='dungeon',certainty='dungeon_reference')
    hints=rows(db,'SELECT DISTINCT * FROM monster_territory_hints WHERE monster_id=?',(ident,))
    covered={p['world_id'] for p in hints}
    for hint in hints:
        hint.update(relation='family',certainty='family_hint',map_name=hint.get('world_name'))
    for hint in rows(db,'SELECT DISTINCT world_id,world_name FROM monster_family_ecosystem_hints WHERE monster_id=?',(ident,)):
        if hint['world_id'] in covered:continue
        hint.update(enrich_world(db,hint['world_id']))
        hint.update(relation='family',certainty='family_hint')
        hints.append(hint)
    return places+hints

def api(db, path, p):
    if p.get('kind',[''])[0]=='locations':
        if path=='/api/search': return locations.search(db,p)
        if path=='/api/detail': return locations.detail(db,p)
        raise ValueError('Page inconnue')
    if path=='/api/item-categories':
        nodes=rows(db,"SELECT c.id,c.parent_id,c.sort_order,t.text name,COUNT(a.id) direct_count FROM item_types c LEFT JOIN translations t ON t.entity='item_types' AND t.entity_id=c.id AND t.field='title' AND t.language='fr' LEFT JOIN all_items a ON a.type_id=c.id GROUP BY c.id ORDER BY c.sort_order,c.id")
        children={}
        for node in nodes: children.setdefault(node['parent_id'],[]).append(node)
        def subtree(node):
            node['children']=[subtree(child) for child in children.get(node['id'],[])]
            node['count']=node['direct_count']+sum(child['count'] for child in node['children'])
            node['children']=[child for child in node['children'] if child['count']]
            return node
        return [node for node in (subtree(n) for n in children.get(0,[])) if node['count']]
    if path=='/api/recipe-jobs':
        return rows(db,"SELECT c.id,t.text name,COUNT(r.id) count FROM recipe_categories c LEFT JOIN translations t ON t.entity='recipe_categories' AND t.entity_id=c.id AND t.field='title' AND t.language='fr' LEFT JOIN recipes r ON r.categoryId=c.id GROUP BY c.id ORDER BY fold(t.text)")
    if path=='/api/stats':
        manifest=json.loads(db.execute("SELECT value FROM metadata WHERE key='manifest'").fetchone()[0])
        return {'version':manifest['version'], 'build':manifest['client_export']['build'], 'bytes':(ROOT/'wakfu.sqlite').stat().st_size,
                'counts':{k:db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for k,t in [('items','all_items'),('monsters','ui_monsters'),('npcs','ui_npcs'),('creatures','ui_unclassified'),('recipes','recipes'),('dungeons','client_dungeons'),('resources','resources')]}}
    kind=p.get('kind',['items'])[0]
    if kind not in ('items','monsters','npcs','creatures','recipes','dungeons','resources'): raise ValueError('Catégorie inconnue')
    if path=='/api/search':
        q=fold(p.get('q',[''])[0]).strip()
        lo=int(p.get('min',['-2147483648'])[0] or -2147483648); hi=int(p.get('max',['2147483647'])[0] or 2147483647)
        offset=max(0,int(p.get('offset',['0'])[0])); order=p.get('sort',['level'])[0]
        if kind=='items':
            sql=NAMES+"SELECT a.id,a.id item_id,a.type_id category_id,n.name,a.level,a.rarity,t.text category FROM all_items a LEFT JOIN names n ON n.id=a.id LEFT JOIN translations t ON t.entity='item_types' AND t.entity_id=a.type_id AND t.language='fr' AND t.field='title'"
        elif kind=='recipes':
            sql=NAMES+"SELECT r.id,rr.productedItemId item_id,n.name,r.level,r.categoryId category_id,a.rarity,t.text category FROM recipes r JOIN recipe_results rr ON rr.recipeId=r.id LEFT JOIN all_items a ON a.id=rr.productedItemId LEFT JOIN names n ON n.id=rr.productedItemId LEFT JOIN translations t ON t.entity='recipe_categories' AND t.entity_id=r.categoryId AND t.language='fr' AND t.field='title'"
        elif kind=='npcs':
            sql="SELECT id,name,level,category,record_id display_id FROM ui_npcs"
        else:
            table,entity,level={'monsters':('ui_monsters','client_monsters','a.level_min'),'creatures':('ui_unclassified','client_monsters','a.level_min'), 'dungeons':('client_dungeons','client_dungeons','a.minimum_level'),'resources':('resources','resources','NULL')}[kind]
            sql=f"SELECT a.id,t.text name,{level} level FROM {table} a LEFT JOIN translations t ON t.entity='{entity}' AND t.entity_id=a.id AND t.language='fr' AND t.field='title'"
        where=" WHERE (fold(COALESCE(name,'')) LIKE ? ESCAPE '\\' OR CAST(abs(id) AS TEXT)=?) AND (level IS NULL OR level BETWEEN ? AND ?)"
        escaped=q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        args=('%'+escaped+'%',q,lo,hi)
        if kind in ('items','recipes') and p.get('favorites',['0'])[0]=='1':
            where+=' AND item_id IN (SELECT item_id FROM personal.item_preferences WHERE favorite=1)'
        if kind=='recipes' and p.get('jobs',[''])[0]:
            jobs=sorted({int(x) for x in p['jobs'][0].split(',')})
            if len(jobs)>100: raise ValueError('Trop de métiers sélectionnés')
            where+=' AND category_id IN ('+','.join('?' for _ in jobs)+')'
            args+=tuple(jobs)
        if kind=='items' and p.get('categories',[''])[0]:
            selected=sorted({int(x) for x in p['categories'][0].split(',')})
            if len(selected)>500: raise ValueError('Trop de catégories sélectionnées')
            where+=' AND category_id IN (WITH RECURSIVE branch(id) AS (SELECT id FROM item_types WHERE id IN ('+','.join('?' for _ in selected)+') UNION SELECT c.id FROM item_types c JOIN branch b ON c.parent_id=b.id) SELECT id FROM branch)'
            args+=tuple(selected)
        if kind in ('items','recipes') and p.get('rarities',[''])[0]:
            rarities=sorted({int(x) for x in p['rarities'][0].split(',')})
            if any(r not in range(8) for r in rarities): raise ValueError('Rareté inconnue')
            where+=' AND rarity IN ('+','.join('?' for _ in rarities)+')'
            args+=tuple(rarities)
        if kind in ('items','recipes') and p.get('learning',[''])[0]:
            learning=p['learning'][0]
            if learning not in ('learnable','unlearned','learned','not_learnable'): raise ValueError('Filtre apprentissage invalide')
            where+=' AND item_id IN (SELECT id FROM item_learning WHERE learn_furniture=?)'
            args+=(0 if learning=='not_learnable' else 1,)
            if learning in ('unlearned','learned'):
                where+=' AND item_id '+('IN' if learning=='learned' else 'NOT IN')+' (SELECT item_id FROM personal.item_preferences WHERE learned=1)'
        if kind=='recipes' and p.get('exclude',[''])[0]:
            excluded=sorted({int(x) for x in p['exclude'][0].split(',')})
            if len(excluded)>100 or any(i<=0 for i in excluded):
                raise ValueError('Sélection invalide (100 ingrédients maximum).')
            if p.get('recursive',['0'])[0]=='1':
                allowed=allowed_recipes(db,set(excluded))
                db.execute('CREATE TEMP TABLE IF NOT EXISTS allowed_recipe_filter (id INTEGER PRIMARY KEY)')
                db.execute('DELETE FROM allowed_recipe_filter')
                db.executemany('INSERT INTO allowed_recipe_filter VALUES (?)',((r,) for r in allowed))
                where+=' AND id IN (SELECT id FROM allowed_recipe_filter)'
            else:
                where+=' AND NOT EXISTS (SELECT 1 FROM recipe_ingredients excluded_ingredient WHERE excluded_ingredient.recipeId=catalog.id AND excluded_ingredient.itemId IN ('+','.join('?' for _ in excluded)+'))'
                args+=tuple(excluded)
        if kind=='dungeons' and p.get('wanted_items',[''])[0]:
            wanted=dungeons.parse_wanted(p['wanted_items'][0])
            where+=' AND EXISTS (SELECT 1 FROM dungeon_monsters wanted_dm JOIN monster_drops wanted_drop ON wanted_drop.monster_id=wanted_dm.monster_id WHERE wanted_dm.dungeon_id=catalog.id AND wanted_drop.item_id IN ('+','.join('?' for _ in wanted)+'))'
            args+=tuple(wanted)
        base='SELECT * FROM ('+sql+') AS catalog'+where
        count=db.execute('SELECT COUNT(*) FROM ('+base+')',args).fetchone()[0]
        sorting={'name':'fold(name),id','level':'level IS NULL,level,id','level_desc':'level IS NULL,level DESC,id'}.get(order,'level IS NULL,level,id')
        results=rows(db,base+' ORDER BY '+sorting+' LIMIT 36 OFFSET ?',args+(offset,))
        for r in results:
            r['image_url']=image_url(db,kind,r['id'])
            if kind in ('items','recipes'): r.update(personal_fields(db,r['item_id']))
        if kind=='dungeons': dungeons.attach_loot(db,results,p.get('loot_categories',[''])[0],p.get('loot_mode',['include'])[0],p.get('loot_rarities',[''])[0])
        return {'total':count,'rows':results}
    if path!='/api/detail': raise ValueError('Page inconnue')
    ident=int(p.get('id',['0'])[0])
    if kind=='npcs':
        found=rows(db,'SELECT * FROM ui_npcs WHERE id=?',(ident,))
        if not found: raise ValueError('PNJ introuvable')
        result=found[0]; result.update(kind=kind,display_id=result['record_id'],image_url=image_url(db,kind,ident))
        if result['record_entity']=='client_protectors':
            result['locations']=rows(db,"SELECT p.world_id,p.x,p.y,p.z,t.text world_name FROM map_points p LEFT JOIN translations t ON t.entity='world_instances' AND t.entity_id=p.world_id AND t.field='title' AND t.language='fr' WHERE p.link_kind=3 AND p.link_id=? AND (p.version_major<1 OR (p.version_major=1 AND p.version_minor<=?)) AND EXISTS (SELECT 1 FROM json_each((SELECT payload FROM source_records WHERE dataset='map_points' AND json_extract(payload,'$.id')=p.id LIMIT 1),'$.descriptions') d WHERE json_extract(d.value,'$.criterion')!='False')",(result['record_id'],int(json.loads(db.execute("SELECT value FROM metadata WHERE key='manifest'").fetchone()[0])['version'].split('.')[1])))
        else: result['locations']=[]
        return result
    table={'items':'all_items','monsters':'ui_monsters','creatures':'ui_unclassified','recipes':'recipes','dungeons':'client_dungeons','resources':'resources'}[kind]
    found=rows(db,'SELECT * FROM '+table+' WHERE id=?',(ident,))
    if not found: raise ValueError('Fiche introuvable')
    raw=found[0]; result={'id':ident,'kind':kind,'name':item_name(db,ident) if kind=='items' else title(db,'client_monsters' if kind in ('monsters','creatures') else table,ident),'level':raw.get('level',raw.get('level_min',raw.get('minimum_level'))),'image_url':image_url(db,kind,ident)}
    if kind=='items':
        result.update(personal_fields(db,ident))
        result['rarity']=raw['rarity']
        desc=db.execute("SELECT text FROM translations WHERE entity IN ('items','job_items') AND entity_id=? AND field='description' AND language='fr' ORDER BY entity LIMIT 1",(ident,)).fetchone()
        result['description']=desc[0] if desc else ''
        result['category']=title(db,'item_types',raw['type_id'])
        sources=rows(db,'SELECT DISTINCT source_kind,source_id FROM acquisition_sources WHERE item_id=?',(ident,))
        for s in sources:
            k=s['source_kind']; sid=s['source_id']
            if k=='recipe':
                rr=db.execute('SELECT productedItemId FROM recipe_results WHERE recipeId=? LIMIT 1',(sid,)).fetchone()
                recipe=db.execute('SELECT categoryId,level FROM recipes WHERE id=?',(sid,)).fetchone()
                s.update(kind='recipes',id=sid,name=item_name(db,rr[0]) if rr else None,label='Fabrication',category=title(db,'recipe_categories',recipe[0]) if recipe else None,level=recipe[1] if recipe else None)
            elif k.startswith('monster'):
                s.update(kind=creature_kind(db,sid),id=sid,name=title(db,'client_monsters',sid),label='Butin de créature' if k=='monster_drop' else 'Récolte sur créature')
            else:
                h=db.execute('SELECT resourceId,skillLevelRequired FROM harvest_actions WHERE id=?',(sid,)).fetchone()
                s.update(kind='resources',id=h[0] if h else sid,name=title(db,'resources',h[0]) if h else None,label='Récolte',level=h[1] if h else None)
        result['sources']=list({(s['kind'],s['id'],s['label'],s.get('level')):s for s in sources}.values())
        result['places']=[]
        for source in result['sources']:
            if source['kind'] not in ('monsters','creatures','npcs'): continue
            source['places']=creature_places(db,source['id'])
            for place in source['places']:
                result['places'].append(dict(place,source_name=source['name'],source_kind=source['kind'],source_id=source['id'],source_label=source['label']))

        result['used_in']=item_links(db,"SELECT r.id AS recipe_id,rr.productedItemId id,i.quantity,r.level,r.categoryId category_id,t.text category FROM recipe_ingredients i JOIN recipes r ON r.id=i.recipeId JOIN recipe_results rr ON rr.recipeId=r.id LEFT JOIN translations t ON t.entity='recipe_categories' AND t.entity_id=r.categoryId AND t.field='title' AND t.language='fr' WHERE i.itemId=? ORDER BY r.level,r.id,rr.productOrder",ident)
        result['effects']=rows(db,"SELECT i.kind,i.ordinal,e.action_id,t.text description,e.payload FROM item_effects i JOIN effects e ON e.id=i.effect_id LEFT JOIN translations t ON t.entity='actions' AND t.entity_id=e.action_id AND t.field='description' AND t.language='fr' WHERE i.item_id=?",(ident,))
        result['formatted_effects']=formatted_effects(db,result['effects'],raw['level'])
    elif kind in ('monsters','creatures'):
        result['family']=title(db,'monster_families',raw['family_id']); result['level_max']=raw['level_max']
        result['places']=creature_places(db,ident)
        result['stats']={k:raw[k] for k in ('base_hp','base_ap','base_mp','base_wp')}
        result['locations']=rows(db,'SELECT DISTINCT * FROM monster_dungeon_locations WHERE monster_id=?',(ident,))
        result['hints']=rows(db,'SELECT DISTINCT world_id,world_name FROM monster_family_ecosystem_hints WHERE monster_id=?',(ident,))
        result['drops']=item_links(db,'SELECT item_id id,rate_raw FROM monster_drops WHERE monster_id=? ORDER BY ordinal',ident)
        result['spells']=rows(db,"SELECT s.*,t.text name FROM monster_spells s LEFT JOIN translations t ON t.entity='monster_spell_names' AND t.entity_id=s.spell_id AND t.field='title' AND t.language='fr' WHERE s.monster_id=?",(ident,))
    elif kind=='recipes':
        result['category']=title(db,'recipe_categories',raw['categoryId'])
        result['ingredients']=item_links(db,'SELECT itemId id,quantity FROM recipe_ingredients WHERE recipeId=? ORDER BY ingredientOrder',ident)
        result['products']=item_links(db,'SELECT productedItemId id,productedItemQuantity quantity FROM recipe_results WHERE recipeId=?',ident)
        result['name']=result['products'][0]['name'] if result['products'] else None
        if result['products']: result.update(personal_fields(db,result['products'][0]['id']))
        product=db.execute('SELECT a.rarity FROM recipe_results r JOIN all_items a ON a.id=r.productedItemId WHERE r.recipeId=? ORDER BY productOrder LIMIT 1',(ident,)).fetchone()
        result['rarity']=product[0] if product else None
    elif kind=='dungeons':
        result['world']=title(db,'world_instances',raw['world_map_id'])
        result['entrances']=rows(db,'SELECT * FROM dungeon_entrances WHERE dungeon_id=?',(ident,))
        result['monsters']=rows(db,"SELECT m.id,t.text name,m.level_min level FROM dungeon_monsters d JOIN client_monsters m ON m.id=d.monster_id LEFT JOIN translations t ON t.entity='client_monsters' AND t.entity_id=m.id AND t.field='title' AND t.language='fr' WHERE d.dungeon_id=?",(ident,))
        for m in result['monsters']: m['kind']=creature_kind(db,m['id'])
    else:
        result['category']=title(db,'resource_types',raw['resourceType'])
        actions=rows(db,'SELECT * FROM harvest_actions WHERE resourceId=?',(ident,))
        for h in actions:
            h['item_name']=item_name(db,h['collectItemId'])
            h['loots']=item_links(db,'SELECT itemId id,quantityMin,quantityMax FROM harvest_loots WHERE listId=? AND itemIsLootList=0',h['collectLootListId'])
        result['harvests']=actions
    return result

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(WEB),**kw)
    def do_POST(self):
        if self.path!='/api/cart-calculate' and (self.connection.getsockname()[0]!='127.0.0.1' or self.client_address[0]!='127.0.0.1'):
            self.send_error(403,'Read-only network access'); return
        if self.path not in ('/api/preference','/api/cart-calculate','/api/initialize'): self.send_error(404); return
        expected=f'http://{self.connection.getsockname()[0]}:{self.server.server_port}'
        if self.headers.get('Origin')!=expected or self.headers.get('Content-Type','').split(';')[0]!='application/json':
            self.send_error(403); return
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=32768: raise ValueError('Requête trop volumineuse')
            data=json.loads(self.rfile.read(size))
            if not isinstance(data,dict): raise ValueError('Requête invalide')
            if self.path=='/api/initialize':
                result=INITIALIZATION.start()
            elif not (ROOT/'wakfu.sqlite').is_file():
                self.send_json({'error':'Initialisez la base WAKFU.','initialize_url':'/initialisation'},503); return
            elif self.path=='/api/cart-calculate':
                with closing(sqlite3.connect((ROOT/'wakfu.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
                    db.row_factory=sqlite3.Row
                    prepare_catalog(db)
                    result=calculate_cart(db,data)
                    for ingredient in result['base']:
                        try:
                            detail=api(db,'/api/detail',{'kind':['items'],'id':[str(ingredient['id'])]})
                            ingredient.update({key:detail.get(key) for key in ('level','category','rarity','image_url','places','sources')})
                            item=db.execute('SELECT type_id FROM all_items WHERE id=?',(ingredient['id'],)).fetchone()
                            ingredient['category_id']=item[0] if item else None
                        except ValueError:
                            ingredient.update(level=None,category=None,rarity=None,image_url=None,places=[],category_id=None)
            else:
                result=save_preference(data)
            code=200
        except (ValueError,sqlite3.Error) as e:
            result={'error':str(e)};code=400
        payload=json.dumps(result,ensure_ascii=False).encode()
        self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
    def end_headers(self):
        if not self.path.startswith('/api/'):
            self.send_header('Cache-Control','no-store, max-age=0')
        super().end_headers()
    def send_json(self,data,code=200):
        payload=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
    def do_GET(self):
        url=urlsplit(self.path)
        if url.path=='/api/initialization':
            if self.client_address[0]!='127.0.0.1' or self.connection.getsockname()[0]!='127.0.0.1':
                self.send_error(403); return
            self.send_json(INITIALIZATION.status()); return
        if url.path in ('/','/index.html','/panier') and not (ROOT/'wakfu.sqlite').is_file():
            self.send_response(302);self.send_header('Location','/initialisation');self.end_headers();return
        if url.path=='/initialisation':
            self.path='/initialize.html'
            url=urlsplit(self.path)
        if url.path=='/favicon.ico':
            self.path='/favicon.png'
            url=urlsplit(self.path)
        if url.path=='/panier':
            self.path='/index.html'
            url=urlsplit(self.path)
        if not url.path.startswith('/api/'):
            if url.path not in ('/','/index.html','/app.js','/style.css','/cart.js','/cart.css','/favicon.png','/favicon.svg','/initialize.html','/initialize.js','/locations.js','/dungeons.js','/tips.js'):
                self.send_error(404); return
            if 'If-Modified-Since' in self.headers: del self.headers['If-Modified-Since']
            return super().do_GET()
        if not (ROOT/'wakfu.sqlite').is_file():
            self.send_json({'error':'Initialisez la base WAKFU.','initialize_url':'/initialisation'},503); return
        try:
            with closing(sqlite3.connect((ROOT/'wakfu.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
                db.row_factory=sqlite3.Row; db.create_function('fold',1,fold)
                prepare_catalog(db)
                if url.path=='/api/image':
                    p=parse_qs(url.query)
                    target=image_url(db,p.get('kind',[''])[0],int(p.get('id',['0'])[0]))
                    if not target: self.send_error(404); return
                    self.send_response(302); self.send_header('Location',target); self.send_header('Cache-Control','no-store'); self.end_headers(); return
                params=parse_qs(url.query)
                remote=self.connection.getsockname()[0]!='127.0.0.1'
                if remote and (params.get('favorites',['0'])[0]=='1' or params.get('learning',[''])[0] in ('learned','unlearned')):
                    self.send_error(403,'Personal favorites are local only'); return
                data=api(db,url.path,params)
                if remote:
                    def public_data(value):
                        if isinstance(value,dict):
                            return {key:public_data(item) for key,item in value.items() if key not in ('note','favorite','learned')}
                        if isinstance(value,list): return [public_data(item) for item in value]
                        return value
                    data=public_data(data)
            code=200
        except (ValueError,sqlite3.Error) as e:
            data={'error':str(e)}; code=400
        payload=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(payload))); self.end_headers(); self.wfile.write(payload)

if __name__=='__main__':
    initialize_personal()
    parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--lan-host',help='Local network IPv4 address for read-only access')
    args=parser.parse_args()
    if args.lan_host:
        address=ipaddress.ip_address(args.lan_host)
        networks=('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')
        if address.version!=4 or not any(address in ipaddress.ip_network(net) for net in networks):
            parser.error('--lan-host must be a private local-network IPv4 address')
        lan_server=ThreadingHTTPServer((args.lan_host,args.port),Handler)
        threading.Thread(target=lan_server.serve_forever,daemon=True).start()
        print(f'WAKFU Atlas (read-only network) : http://{args.lan_host}:{args.port}',flush=True)
    print(f'WAKFU Atlas : http://127.0.0.1:{args.port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
