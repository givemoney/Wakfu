"""Lossless source records plus normalized scalar columns and relations; no inferred game data."""
import datetime, json, pathlib, sqlite3
TABLES = {'actions':'actions','collectibleResources':'harvest_actions','equipmentItemTypes':'equipment_types','harvestLoots':'harvest_loots','itemProperties':'item_properties','jobsItems':'job_items','recipeCategories':'recipe_categories','recipeIngredients':'recipe_ingredients','recipeResults':'recipe_results','recipes':'recipes','resourceTypes':'resource_types','resources':'resources','states':'states','recipePattern':'recipe_patterns'}
def dump(x): return json.dumps(x,ensure_ascii=False,separators=(',',':'))
def q(x): return '"'+x.replace('"','""')+'"'
def build(folder, destination):
    db=sqlite3.connect(destination)
    try: return _build(folder,destination,db)
    finally: db.close()
def _build(folder, destination, db):
    folder=pathlib.Path(folder); manifest=json.loads((folder/'manifest.json').read_text('utf-8'))
    data={p.stem:json.loads(p.read_bytes()) for p in folder.glob('*.json') if p.stem!='manifest'}
    db.executescript('''
    PRAGMA foreign_keys=ON;
    CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE source_records(dataset TEXT, ordinal INTEGER, payload TEXT NOT NULL, PRIMARY KEY(dataset,ordinal));
    CREATE TABLE translations(entity TEXT,entity_id INTEGER,field TEXT,language TEXT,text TEXT,PRIMARY KEY(entity,entity_id,field,language));
    CREATE TABLE arrays(entity TEXT,entity_id INTEGER,field TEXT,ordinal INTEGER,value TEXT,PRIMARY KEY(entity,entity_id,field,ordinal));
    CREATE TABLE effects(id INTEGER PRIMARY KEY,action_id INTEGER,area_shape INTEGER,payload TEXT NOT NULL);
    CREATE TABLE effect_parameters(effect_id INTEGER REFERENCES effects(id),ordinal INTEGER,value REAL,PRIMARY KEY(effect_id,ordinal));
    CREATE TABLE item_effects(item_id INTEGER REFERENCES items(id),kind TEXT,ordinal INTEGER,effect_id INTEGER REFERENCES effects(id),PRIMARY KEY(item_id,kind,ordinal));
    CREATE TABLE item_properties_link(item_id INTEGER REFERENCES items(id),ordinal INTEGER,property_id INTEGER,PRIMARY KEY(item_id,ordinal));
    CREATE TABLE referenced_harvest_skills(id INTEGER PRIMARY KEY);
    CREATE TABLE acquisition_sources(item_id INTEGER,source_kind TEXT,source_id INTEGER,source_dataset TEXT);
    ''')
    def flatten(obj,prefix=''):
        out={}
        for k,v in obj.items():
            key=prefix+k
            if isinstance(v,dict): out.update(flatten(v,key+'_'))
            elif not isinstance(v,list): out[key]=v
        return out
    def table(name,records):
        flattened=[flatten(r) for r in records]; cols=sorted({k for r in flattened for k in r})
        defs=[]
        for col in cols:
            vals=[r[col] for r in flattened if r.get(col) is not None]
            typ='INTEGER' if all(isinstance(v,(int,bool)) for v in vals) else 'REAL' if all(isinstance(v,(float,int)) for v in vals) else 'TEXT'
            defs.append(q(col)+' '+typ+(' PRIMARY KEY' if col=='id' else ''))
        db.execute('CREATE TABLE '+q(name)+'('+','.join(defs)+')')
        db.executemany('INSERT INTO '+q(name)+'('+','.join(map(q,cols))+') VALUES('+','.join('?' for _ in cols)+')',[[r.get(c) for c in cols] for r in flattened])
    def normalize_extras(name,identifier,obj,prefix=''):
        for key,value in obj.items():
            field=prefix+key
            if isinstance(value,list):
                db.executemany('INSERT INTO arrays VALUES(?,?,?,?,?)',[(name,identifier,field,i,dump(v)) for i,v in enumerate(value)])
            elif isinstance(value,dict): normalize_extras(name,identifier,value,field+'_')
    for dataset, records in data.items():
        db.executemany('INSERT INTO source_records VALUES(?,?,?)',[(dataset,i,dump(r)) for i,r in enumerate(records)])
        normalized=[]
        for r in records:
            definition=r.get('definition',r)
            if dataset=='items': definition=definition['item']
            normalized.append(definition)
            identifier=definition.get('id')
            if identifier is not None:
                for field in ('title','description'):
                    if isinstance(r.get(field),dict):
                        db.executemany('INSERT INTO translations VALUES(?,?,?,?,?)',[(TABLES.get(dataset,dataset),identifier,field,lang,text) for lang,text in r[field].items()])
                normalize_extras(TABLES.get(dataset,dataset),identifier,definition)
        table(TABLES.get(dataset,dataset),normalized)
    for r in data['items']:
        item=r['definition']['item']; identifier=item['id']
        for i, prop in enumerate(item.get('properties',[])):
            db.execute('INSERT INTO item_properties_link VALUES(?,?,?)',(identifier,i,prop))
        for kind in ('equipEffects','useEffects','useCriticalEffects'):
            for i, wrapped in enumerate(r['definition'].get(kind,[])):
                eff=wrapped['effect']['definition']; eid=eff['id']; payload=dump(eff)
                existing=db.execute('SELECT payload FROM effects WHERE id=?',(eid,)).fetchone()
                if existing and existing[0]!=payload: raise ValueError('Conflicting effect '+str(eid))
                if not existing:
                    db.execute('INSERT INTO effects VALUES(?,?,?,?)',(eid,eff.get('actionId'),eff.get('areaShape'),payload))
                    db.executemany('INSERT INTO effect_parameters VALUES(?,?,?)',[(eid,j,v) for j,v in enumerate(eff.get('params',[]))])
                db.execute('INSERT INTO item_effects VALUES(?,?,?,?)',(identifier,kind,i,eid))
    db.execute('INSERT INTO referenced_harvest_skills SELECT DISTINCT skillId FROM harvest_actions')
    db.execute("INSERT INTO acquisition_sources SELECT productedItemId,'recipe',recipeId,'recipeResults' FROM recipe_results")
    db.execute("INSERT INTO acquisition_sources SELECT collectItemId,'harvest_direct',id,'collectibleResources' FROM harvest_actions WHERE collectItemId>0")
    db.execute("INSERT INTO acquisition_sources SELECT l.itemId,'harvest_loot',h.id,'harvestLoots' FROM harvest_loots l JOIN harvest_actions h ON h.collectLootListId=l.listId WHERE l.itemIsLootList=0")
    if 'client_monsters' in data:
        db.execute("INSERT INTO acquisition_sources SELECT item_id,'monster_drop',monster_id,'client_monsters' FROM monster_drops WHERE item_id IN (SELECT id FROM items UNION SELECT id FROM job_items)")
        db.execute("INSERT INTO acquisition_sources SELECT collect_item_id,'monster_collect',monster_id,'client_monsters' FROM monster_collect_actions WHERE collect_item_id>0 AND collect_item_id IN (SELECT id FROM items UNION SELECT id FROM job_items)")
        db.execute("INSERT INTO acquisition_sources SELECT e.item_id,'monster_collect_loot',a.monster_id,'client_loot_lists' FROM monster_collect_actions a JOIN loot_list_entries e ON e.list_id=a.collect_loot_list_id WHERE e.item_id IN (SELECT id FROM items UNION SELECT id FROM job_items)")
    db.executescript('''
    CREATE VIEW all_item_ids AS SELECT id FROM items UNION SELECT id FROM job_items;
    CREATE VIEW all_items AS
      SELECT id,level,baseParameters_itemTypeId AS type_id,baseParameters_rarity AS rarity,graphicParameters_gfxId AS gfx_id,'items' AS primary_dataset FROM items
      UNION ALL SELECT id,level,itemTypeId,rarity,graphicParameters_gfxId,'jobsItems' FROM job_items WHERE id NOT IN (SELECT id FROM items);
    CREATE VIEW item_names_fr AS SELECT entity,entity_id AS id,text AS name FROM translations WHERE field='title' AND language='fr' AND entity IN ('items','job_items');
    CREATE INDEX translation_text ON translations(language,text);
    CREATE INDEX ingredients_item ON recipe_ingredients(itemId);
    CREATE INDEX results_item ON recipe_results(productedItemId);
    CREATE INDEX acquisition_item ON acquisition_sources(item_id);
    CREATE INDEX harvest_list ON harvest_loots(listId);
    ''')
    if 'client_monsters' in data:
        db.executescript('''
        CREATE UNIQUE INDEX monster_spell_relation ON monster_spells(monster_id,ordinal);
        CREATE UNIQUE INDEX monster_drop_relation ON monster_drops(monster_id,ordinal);
        CREATE UNIQUE INDEX dungeon_monster_relation ON dungeon_monsters(dungeon_id,ordinal);
        CREATE INDEX monster_drops_item ON monster_drops(item_id);
        CREATE INDEX monster_drops_monster ON monster_drops(monster_id);
        CREATE INDEX dungeon_monsters_monster ON dungeon_monsters(monster_id);
        CREATE INDEX ecosystems_family ON family_ecosystem_references(family_id);
        CREATE VIEW monster_dungeon_locations AS
          SELECT dm.monster_id,dm.dungeon_id,
            d.world_map_id AS associated_world_id,
            e.world_id AS entrance_world_id,e.x AS entrance_x,e.y AS entrance_y,e.z AS entrance_z,
            dn.text AS dungeon_name,wn.text AS associated_world_name
          FROM dungeon_monsters dm JOIN client_dungeons d ON d.id=dm.dungeon_id
          LEFT JOIN dungeon_entrances e ON e.dungeon_id=dm.dungeon_id
          LEFT JOIN translations dn ON dn.entity='client_dungeons' AND dn.entity_id=d.id AND dn.field='title' AND dn.language='fr'
          LEFT JOIN translations wn ON wn.entity='world_instances' AND wn.entity_id=d.world_map_id AND wn.field='title' AND wn.language='fr';
        CREATE VIEW monster_family_ecosystem_hints AS
          SELECT m.id AS monster_id,m.family_id,f.world_id,f.protector_id,wn.text AS world_name
          FROM client_monsters m JOIN family_ecosystem_references f ON f.family_id=m.family_id
          LEFT JOIN translations wn ON wn.entity='world_instances' AND wn.entity_id=f.world_id AND wn.field='title' AND wn.language='fr';
        ''')
    if 'geography_worlds' in data:
        from geography import install_relations
        install_relations(db)
    checks={
      'ingredients_without_recipe':'SELECT COUNT(*) FROM recipe_ingredients WHERE recipeId NOT IN (SELECT id FROM recipes)',
      'results_without_recipe':'SELECT COUNT(*) FROM recipe_results WHERE recipeId NOT IN (SELECT id FROM recipes)',
      'ingredients_unknown_item':'SELECT COUNT(*) FROM recipe_ingredients WHERE itemId NOT IN (SELECT id FROM all_item_ids)',
      'results_unknown_item':'SELECT COUNT(*) FROM recipe_results WHERE productedItemId NOT IN (SELECT id FROM all_item_ids)',
      'recipes_unknown_category':'SELECT COUNT(*) FROM recipes WHERE categoryId NOT IN (SELECT id FROM recipe_categories)',
      'harvest_unknown_resource':'SELECT COUNT(*) FROM harvest_actions WHERE resourceId NOT IN (SELECT id FROM resources)',
      'effects_unknown_action':'SELECT COUNT(*) FROM effects WHERE action_id NOT IN (SELECT id FROM actions)',
      'harvest_unknown_direct_item':'SELECT COUNT(*) FROM harvest_actions WHERE collectItemId>0 AND collectItemId NOT IN (SELECT id FROM all_item_ids)',
      'harvest_loot_unknown_item':'SELECT COUNT(*) FROM harvest_loots WHERE itemIsLootList=0 AND itemId NOT IN (SELECT id FROM all_item_ids)',
      'harvest_missing_loot_list':'SELECT COUNT(*) FROM harvest_actions WHERE collectLootListId>0 AND collectLootListId NOT IN (SELECT listId FROM harvest_loots)',
      'items_without_known_acquisition':'SELECT COUNT(*) FROM all_item_ids WHERE id NOT IN (SELECT item_id FROM acquisition_sources)',
      'harvest_loot_list_references':'SELECT COUNT(*) FROM harvest_loots WHERE itemIsLootList<>0'
    }
    audit={key:db.execute(sql).fetchone()[0] for key,sql in checks.items()}
    if 'client_monsters' in data:
        extra={
          'monster_unknown_family':'SELECT COUNT(*) FROM client_monsters WHERE family_id NOT IN (SELECT id FROM monster_families)',
          'monster_drop_unknown_item':'SELECT COUNT(*) FROM monster_drops WHERE item_id NOT IN (SELECT id FROM all_item_ids)',
          'dungeon_unknown_monster':'SELECT COUNT(*) FROM dungeon_monsters WHERE monster_id NOT IN (SELECT id FROM client_monsters)',
          'monsters_without_dungeon_membership':'SELECT COUNT(*) FROM client_monsters WHERE id NOT IN (SELECT monster_id FROM dungeon_monsters)',
          'monsters_without_direct_dungeon_or_family_hint':'SELECT COUNT(*) FROM client_monsters WHERE id NOT IN (SELECT monster_id FROM dungeon_monsters UNION SELECT monster_id FROM monster_family_ecosystem_hints)',
          'monsters_without_french_name':"SELECT COUNT(*) FROM client_monsters WHERE id NOT IN (SELECT entity_id FROM translations WHERE entity='client_monsters' AND field='title' AND language='fr')",
          'dungeons_without_entrance_coordinates':'SELECT COUNT(*) FROM client_dungeons WHERE id NOT IN (SELECT dungeon_id FROM dungeon_entrances)',
          'ecosystem_unknown_family':'SELECT COUNT(*) FROM family_ecosystem_references WHERE family_id NOT IN (SELECT id FROM monster_families)',
          'dungeon_point_unmatched':"SELECT COUNT(*) FROM map_points p WHERE p.link_kind=2 AND NOT EXISTS (SELECT 1 FROM source_records r,json_each(r.payload,'$.definition.binary.field_8') links WHERE r.dataset='client_dungeons' AND links.value=p.link_id)"
        }
        audit.update({k:db.execute(sql).fetchone()[0] for k,sql in extra.items()})
        audit['monster_collect_unknown_item']=db.execute('SELECT COUNT(*) FROM monster_collect_actions WHERE collect_item_id>0 AND collect_item_id NOT IN (SELECT id FROM all_item_ids)').fetchone()[0]
        audit['monster_collect_missing_loot_list']=db.execute('SELECT COUNT(*) FROM monster_collect_actions WHERE collect_loot_list_id>0 AND collect_loot_list_id NOT IN (SELECT id FROM client_loot_lists)').fetchone()[0]
        for fatal in ('monster_unknown_family','dungeon_unknown_monster','ecosystem_unknown_family'):
            if audit[fatal]:raise ValueError('Broken client relationship '+fatal)
    if 'item_types' in data:
        audit['items_unknown_type']=db.execute('SELECT COUNT(*) FROM all_items WHERE type_id NOT IN (SELECT id FROM item_types)').fetchone()[0]
        audit['types_unknown_parent']=db.execute('SELECT COUNT(*) FROM item_types WHERE parent_id<>0 AND parent_id NOT IN (SELECT id FROM item_types)').fetchone()[0]
        if audit['items_unknown_type'] or audit['types_unknown_parent']: raise ValueError('Incomplete item category hierarchy')
    for fatal in ('ingredients_without_recipe','results_without_recipe','recipes_unknown_category'):
        if audit[fatal]: raise ValueError('Broken structural relationship: '+fatal)
    if 'geography_worlds' in data:
        audit['geography_named_territories']=db.execute('SELECT COUNT(*) FROM geography_territories WHERE name IS NOT NULL').fetchone()[0]
        audit['geography_monsters_with_territory_hint']=db.execute('SELECT COUNT(DISTINCT monster_id) FROM monster_territory_hints').fetchone()[0]
        audit['geography_conflicting_dungeon_entrances_rejected']=manifest['client_export']['geography_conflicts']['rejected_dungeon_entrances']
    counts={name:db.execute('SELECT COUNT(*) FROM '+q(name)).fetchone()[0] for name, in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    counts['metadata']=2
    report={'version':manifest['version'],'counts':counts,'distinct_item_ids':db.execute('SELECT COUNT(*) FROM all_item_ids').fetchone()[0],'audit':audit,'sources':manifest,'limits':{'monsters':'No imported monster dataset; world total unknown','monster_drops':'No imported monster-drop dataset; world total unknown','zones':'No imported zone dataset; world total unknown','jobs':'Recipe categories have official names; harvest skills are referenced IDs only, without invented names','acquisition':'Only recipe results, direct harvest and joined harvest loot; other obtainment sources unknown','effect_text':'Official templates and numeric parameters retained; no unverified template evaluation','scope':'Published CDN snapshot, not proof that each record is obtainable in live game; no exhaustive endpoint directory available'}}
    report['retrieved_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    report['overlap_item_ids']=db.execute('SELECT COUNT(*) FROM items JOIN job_items USING(id)').fetchone()[0]
    report['items_with_known_acquisition']=report['distinct_item_ids']-audit['items_without_known_acquisition']
    report['limits']['endpoint_probes']='HTTP 403 means access denied, not proof of nonexistence. Probed filenames are candidates, not an official exhaustive manifest.'
    report['limits']['types']='32 equipment types and 7 environmental resource types supplied; other item type IDs retained without invented type labels.'
    if 'item_types' in data:
        report['limits']['types']='Full official ITEM_TYPE parent hierarchy and French content.14 translations; missing labels retain numeric IDs; category presence does not guarantee availability in game.'
    if 'client_monsters' in data:
        report['limits'].update({
          'monsters':'Current official CDN creature definitions; includes NPCs, summons, obsolete/test and quest variants, not all necessarily available in play',
          'monster_drops':'Official embedded monster drop entries imported, retaining raw rate and condition vector; no promise of an effective in-game chance',
          'zones':'Official world hierarchy, named territories, territory family requirements and dungeon associations. Contradictory dungeon entrances are excluded; family hints do not prove individual species presence. No invented spawn coordinates',
          'acquisition':'Recipes, resource and creature harvest, and official monster drop entries whose item IDs are present; unknown item references are retained and audited',
          'privacy':'Updater accesses public CDN endpoints and its own folder; no account credentials, game process/memory access or installed-client inspection'
        })
        report['client_export']=manifest.get('client_export')
    db.execute('INSERT INTO metadata VALUES(?,?)',('manifest',dump(manifest)))
    db.execute('INSERT INTO metadata VALUES(?,?)',('report',dump(report)))
    db.commit()
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    for dataset,rows in data.items():
        assert db.execute('SELECT COUNT(*) FROM source_records WHERE dataset=?',(dataset,)).fetchone()[0]==len(rows)
    db.execute('VACUUM'); db.close()
    report['database_bytes']=pathlib.Path(destination).stat().st_size
    return report
