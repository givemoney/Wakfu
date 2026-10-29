"""Dungeon loot derived exclusively from explicit dungeon-monster-drop relations."""
import math

def loot_order(item):
    rarity=item["rarity"]
    rank=rarity if isinstance(rarity,int) and rarity in range(8) else -1
    rate=item["drop_rate_raw"]
    return (-rank, rate is None, rate if rate is not None else 0, (item["name"] or "").casefold(), item["id"])

def attach_loot(db, dungeons, categories='', mode='include', rarities=''):
    selected=sorted({int(x) for x in categories.split(',') if x})
    if len(selected)>200 or any(x<=0 for x in selected):
        raise ValueError('Sélection de catégories invalide.')
    if mode not in ('include','exclude'): raise ValueError('Filtre de butin invalide.')
    selected_rarities={int(x) for x in rarities.split(',') if x}
    if any(x not in range(8) for x in selected_rarities): raise ValueError('Rareté invalide.')
    allowed=set()
    if selected:
        marks=','.join('?' for _ in selected)
        allowed={r[0] for r in db.execute('WITH RECURSIVE branch(id) AS (SELECT id FROM item_types WHERE id IN ('+marks+') UNION SELECT t.id FROM item_types t JOIN branch b ON t.parent_id=b.id) SELECT id FROM branch',selected)}
    indexed={d['id']:{} for d in dungeons}
    if not indexed:return
    marks=','.join('?' for _ in indexed)
    sql="""WITH names AS (SELECT id,MAX(name) name FROM item_names_fr GROUP BY id)
      SELECT DISTINCT dm.dungeon_id,md.item_id id,a.id IS NOT NULL known,a.level,a.type_id,a.rarity,a.gfx_id,n.name,
        t.text category,md.monster_id,mt.text monster_name,md.rate_raw
      FROM dungeon_monsters dm JOIN monster_drops md ON md.monster_id=dm.monster_id
      LEFT JOIN all_items a ON a.id=md.item_id LEFT JOIN names n ON n.id=md.item_id
      LEFT JOIN translations t ON t.entity='item_types' AND t.entity_id=a.type_id AND t.field='title' AND t.language='fr'
      LEFT JOIN translations mt ON mt.entity='client_monsters' AND mt.entity_id=md.monster_id AND mt.field='title' AND mt.language='fr'
      WHERE dm.dungeon_id IN ("""+marks+") ORDER BY a.level IS NULL,a.level,n.name,md.item_id,md.monster_id"
    for row in db.execute(sql,tuple(indexed)):
        r=dict(row);items=indexed[r.pop('dungeon_id')]
        monster={'id':r.pop('monster_id'),'name':r.pop('monster_name')}
        rate=r.pop('rate_raw')
        item=items.setdefault(r['id'],{**r,'sources':[],'drop_rate_raw':None})
        if isinstance(rate,(int,float)) and math.isfinite(rate) and rate>=0:
            item['drop_rate_raw']=max(item['drop_rate_raw'],rate) if item['drop_rate_raw'] is not None else rate
        if monster not in item['sources']:item['sources'].append(monster)
    for dungeon in dungeons:
        all_loot=list(indexed[dungeon['id']].values())
        dungeon['unresolved_loot']=sum(not item['known'] for item in all_loot)
        known=sorted((item for item in all_loot if item['known']),key=loot_order)
        dungeon['loot_total']=len(known)
        dungeon['loot']=[item for item in known if (not selected or ((item['type_id'] in allowed)==(mode=='include'))) and (not selected_rarities or item['rarity'] in selected_rarities)]


def parse_wanted(value):
    try:
        selected=sorted({int(x) for x in value.split(',')})
    except ValueError:
        raise ValueError('Liste d’objets recherchés invalide.') from None
    if len(selected)>100 or any(x<=0 or x>2147483647 for x in selected):
        raise ValueError('Liste invalide : 100 objets maximum.')
    return selected
