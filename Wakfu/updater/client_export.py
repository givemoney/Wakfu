"""Export only the current public Ankama CDN files. Never reads an installed game."""
import collections,hashlib,json,pathlib,re,tempfile,zipfile
from cytrus import download_selected,published
from client_binary import document
from java_schema import current_schemas
from map_points import points
from geography import datasets as geography_datasets
from furniture_learning import learning_records
FILES=['lib/wakfu-client.jar','contents/bdata/35.jar','contents/bdata/37.jar','contents/bdata/42.jar','contents/bdata/47.jar','contents/bdata/119.jar','contents/bdata/39.jar','contents/bdata/75.jar','contents/bdata/54.jar','contents/maps/data.jar','contents/maps/paper/full.jar','contents/i18n/i18n_fr.jar']
def unescape(s):
    def replacement(m):
        token=m[0]
        if token.startswith('\\u'):return chr(int(token[2:],16))
        return {'\\n':'\n','\\r':'\r','\\t':'\t','\\f':'\f'}.get(token,token[1:])
    return re.sub(r'\\u[0-9a-fA-F]{4}|\\.',replacement,s)
def export(directory,game_version,client_root=None,download_manifest=None):
    directory=pathlib.Path(directory)
    if client_root is None:
        with tempfile.TemporaryDirectory(prefix='.official-files-',dir=directory) as tmp:
            meta=download_selected(tmp,FILES)
            result=export(directory,game_version,tmp,meta)
            current=published()[0]
            if current!=meta['build']:raise ValueError('Official client build changed during import')
            return result
    root=pathlib.Path(client_root);meta=download_manifest
    if meta is None:raise ValueError('A verified CDN download manifest is required')
    if not meta['build'].split('_',1)[1].startswith('.'.join(game_version.split('.')[:3])+'.'):
        raise ValueError('Client and JSON release mismatch')
    for name,record in meta['files'].items():
        if hashlib.sha1((root/name).read_bytes()).hexdigest()!=record['sha1']:raise ValueError('Changed downloaded file '+name)
    defs,types,mapping,classes=current_schemas(root)
    def read(name):return document(root/'contents/bdata'/f'{types[name]}.jar',mapping[name],defs,{mapping[name]:types[name]})
    with zipfile.ZipFile(root/'contents/i18n/i18n_fr.jar') as z:text=z.read('texts_fr.properties').decode('utf8')
    names={}
    for line in text.splitlines():
        m=re.match(r'content\.(\d+)\.(\d+)=(.*)',line)
        if m:names[(int(m[1]),int(m[2]))]=unescape(m[3])
    def title(kind,identifier):
        value=names.get((kind,identifier));return {'fr':value} if value is not None else {}
    monsters=read('MONSTER');families=read('MONSTER_TYPE');dungeons=read('DUNGEON');protectors=read('PROTECTOR');lootlists=read('LOOT_LIST');worldloots=read('WORLD_LOOT_LIST')
    item_types=read('ITEM_TYPE')
    by_id={r['field_0']:r for r in item_types}
    if len(by_id)!=len(item_types): raise ValueError('Duplicate item type')
    for ident,r in by_id.items():
        seen={ident}; parent=r['field_1']
        while parent:
            if parent not in by_id or parent in seen: raise ValueError('Broken item type hierarchy')
            seen.add(parent); parent=by_id[parent]['field_1']
    datasets=geography_datasets(root,names)
    datasets['item_learning']=learning_records(root,(defs,types,mapping,classes))
    datasets['item_types']=[{'definition':{'id':r['field_0'],'parent_id':r['field_1'],'sort_order':r['field_7'],'binary':r},'title':title(14,r['field_0'])} for r in item_types]
    datasets['client_monsters']=[{'definition':{'id':r['field_0'],'family_id':r['field_1'],'level_min':r['field_2'],'level_max':r['field_3'],'base_hp':r['field_6'],'base_wp':r['field_7'],'base_ap':r['field_8'],'base_mp':r['field_9'],'gfx_id':r['field_89'],'binary':r},'title':title(7,r['field_0'])} for r in monsters]
    datasets['monster_families']=[{'definition':{'id':r['field_0'],'parent_id':r['field_1'],'kind':r['field_2'],'binary':r},'title':title(38,r['field_0'])} for r in families]
    datasets['client_dungeons']=[{'definition':{'id':r['field_0'],'minimum_level':r['field_1'],'world_map_id':r['field_3'],'instance_ids':r['field_4'],'monster_ids':r['field_13'],'binary':r},'title':title(137,r['field_0'])} for r in dungeons]
    datasets['client_protectors']=[{'definition':{'id':r['field_0'],'monster_id':r['field_1'],'binary':r},'title':title(48,r['field_0'])} for r in protectors]
    datasets['client_loot_lists']=[{'id':r['field_0'],'binary':r} for r in lootlists]
    datasets['client_world_loot_lists']=[{'id':r['field_0'],'binary':r} for r in worldloots]
    datasets['monster_spells']=[{'monster_id':r['field_0'],'ordinal':i,'spell_id':spell['field_0'],'spell_level':spell['field_1']} for r in monsters for i,spell in enumerate(r['field_69'])]
    datasets['monster_spell_names']=[{'definition':{'id':sid},'title':title(3,sid)} for sid in sorted({s['spell_id'] for s in datasets['monster_spells']})]
    datasets['monster_drops']=[{'monster_id':r['field_0'],'ordinal':i,'item_id':drop['field_0'],'rate_raw':drop['field_7'],'conditions_raw':drop['field_8'],'binary':drop} for r in monsters for i,drop in enumerate(r['field_82'])]
    datasets['monster_collect_actions']=[{'monster_id':r['field_0'],'ordinal':i,'action_id':a['field_0'],'skill_id':a['field_1'],'skill_level_required':a['field_2'],'collect_loot_list_id':a['field_6'],'collect_item_id':a['field_8'],'binary':a} for r in monsters for i,a in enumerate(r['field_76'])]
    datasets['loot_list_entries']=[{'list_id':r['field_0'],'ordinal':i,'entry_id':a['field_0'],'item_id':a['field_1'],'rate_raw':a['field_2'],'criterion':a['field_3'],'binary':a} for r in lootlists for i,a in enumerate(r['field_2'])]
    datasets['dungeon_monsters']=[{'dungeon_id':r['field_0'],'ordinal':i,'monster_id':mid} for r in dungeons for i,mid in enumerate(r['field_13'])]
    poi,ies=points(root);datasets['map_points']=poi;datasets['map_interactive_points']=ies
    # Current-version visibility check mirrors bLa.c(); criteria themselves remain unevaluated.
    def current_point(p):
        return (p['version_major']<1 or (p['version_major']==1 and p['version_minor']<=int(game_version.split('.')[1]))) and any(d['criterion']!='False' for d in p['descriptions'])
    dungeon_ids={d['field_0'] for d in dungeons}
    # bLa.d resolves the landmark link through eQN.QO, not dungeon ID directly.
    # eQN.e/eQO registers aKU.cnk (field_8), the dungeon's landmark link IDs.
    entrance_links={}
    for d in dungeons:
        for link_id in d['field_8']:
            if link_id in entrance_links and entrance_links[link_id]!=d['field_0']:raise ValueError('Ambiguous dungeon landmark link')
            entrance_links[link_id]=d['field_0']
    datasets['dungeon_entrances']=[{'dungeon_id':entrance_links[p['link_id']],'point_id':p['id'],'world_id':p['world_id'],'x':p['x'],'y':p['y'],'z':p['z'],'criteria':[d['criterion'] for d in p['descriptions']]} for p in poi if p['link_kind']==2 and p['link_id'] in entrance_links and current_point(p)]
    # Validate correctly resolved POI links against the associated official world.
    geography_by_id={w['id']:w for w in datasets['geography_worlds']}
    dungeon_world={d['field_0']:d['field_3'] for d in dungeons}
    def consistent_entrance(e):
        associated=geography_by_id.get(dungeon_world[e['dungeon_id']])
        entrance=geography_by_id.get(e['world_id'])
        return bool(associated and entrance and associated['region_id']==entrance['region_id'])
    rejected=[e for e in datasets['dungeon_entrances'] if not consistent_entrance(e)]
    meta['geography_conflicts']={'rejected_dungeon_entrances':len(rejected),'records':rejected,
      'rule':'Entry and associated dungeon world must have the same official root world. Conflicts remain in raw map_points, not in displayed locations.'}
    datasets['dungeon_entrances']=[e for e in datasets['dungeon_entrances'] if consistent_entrance(e)]
    protector_by_id={r['field_0']:r for r in protectors}
    # A family's ecosystem requirement is not proof that each variant/boss spawns there.
    habitats=[]
    for p in poi:
        if p['link_kind']!=3 or p['link_id'] not in protector_by_id or not current_point(p):continue
        protector=protector_by_id[p['link_id']]
        for f in protector['field_14']:
            habitats.append({'family_id':f['field_0'],'world_id':p['world_id'],'protector_id':p['link_id'],'point_id':p['id'],'population_min':f['field_1'],'population_max':f['field_2'],'criteria':[d['criterion'] for d in p['descriptions']]})
    datasets['family_ecosystem_references']=habitats
    world_ids={r['id'] for r in datasets['geography_worlds']}|{p['world_id'] for p in poi}|{r['field_3'] for r in dungeons}|{w for r in dungeons for w in r['field_4']}
    datasets['world_instances']=[{'definition':{'id':wid},'title':title(77,wid)} for wid in sorted(world_ids)]
    for name,rows in datasets.items():
        if not rows:raise ValueError('Empty required client dataset '+name)
        (directory/(name+'.json')).write_text(json.dumps(rows,ensure_ascii=False,separators=(',',':')),encoding='utf8')
    meta['datasets']={k:len(v) for k,v in datasets.items()}
    meta['name_source']='Official content.{translation_type}.{id} entries in downloaded texts_fr.properties'
    meta['schema_source']='Fields and types read from the downloaded current wakfu-client.jar; every record boundary validated'
    from harvest_locations import references
    location_reference={'format':1,'version':game_version,'build':meta['build'],
        'source':meta['manifest_url'],'archive':'contents/maps/data.jar',
        'sha1':meta['files']['contents/maps/data.jar']['sha1'],
        'links':references(root/'contents/maps/data.jar')}
    (directory/'harvest-locations.snapshot').write_text(json.dumps(location_reference,ensure_ascii=False,indent=2),encoding='utf-8')
    meta['limits']=['Creature definitions include NPCs, summons, quest variants, test content and obsolete records; not a list of all currently fightable enemies','Dungeon monster membership is explicit; parent world is an associated world, not always the entry coordinate','Ecosystem references describe family population requirements, not exact per-species spawn points','Map descriptions may contain unevaluated access criteria; no guarantee of access','Anonymous fields, raw drop condition vectors, and world loot definitions are preserved without inferred semantics']
    return meta
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--version',required=True);a=p.parse_args()
    print(json.dumps(export(a.directory,a.version),indent=2))
