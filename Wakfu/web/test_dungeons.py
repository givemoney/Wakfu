import sqlite3
import unittest
from dungeons import attach_loot

class DungeonLootTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
        self.db.executescript("""
        CREATE TABLE item_types(id,parent_id);
        INSERT INTO item_types VALUES(1,0),(2,1),(3,0);
        CREATE TABLE dungeon_monsters(dungeon_id,monster_id);
        INSERT INTO dungeon_monsters VALUES(10,100),(10,101),(11,102);
        CREATE TABLE monster_drops(item_id,monster_id,rate_raw);
        INSERT INTO monster_drops VALUES(20,100,0.01),(20,100,0.01),(20,101,0.02),(21,100,0.1),(22,102,0.1);
        CREATE TABLE all_items(id,level,type_id,rarity,gfx_id);
        INSERT INTO all_items VALUES(20,5,2,1,2),(21,7,3,2,3),(22,9,3,2,4);
        CREATE TABLE item_names_fr(id,name);
        INSERT INTO item_names_fr VALUES(20,'Objet A'),(21,'Objet B'),(22,'Autre donjon');
        CREATE TABLE translations(entity,entity_id,field,language,text);
        """)
    def tearDown(self):self.db.close()
    def test_deduplication_sources_and_no_cross_dungeon_leak(self):
        ds=[{'id':10},{'id':12}];attach_loot(self.db,ds)
        self.assertEqual([i['id'] for i in ds[0]['loot']],[21,20])
        self.assertEqual(len(next(i for i in ds[0]['loot'] if i['id']==20)['sources']),2)
        self.assertEqual(ds[1]['loot'],[])
    def test_parent_category_include_and_exclude(self):
        ds=[{'id':10}];attach_loot(self.db,ds,'1','include')
        self.assertEqual([i['id'] for i in ds[0]['loot']],[20]);self.assertEqual(ds[0]['loot_total'],2)
        attach_loot(self.db,ds,'1','exclude');self.assertEqual([i['id'] for i in ds[0]['loot']],[21])
    def test_empty_selection_displays_all(self):
        ds=[{'id':10}];attach_loot(self.db,ds,'','exclude');self.assertEqual(len(ds[0]['loot']),2)
    def test_invalid_mode_rejected(self):
        with self.assertRaises(ValueError):attach_loot(self.db,[{'id':10}],mode='invalid')

    def test_unresolved_items_are_counted_but_not_displayed(self):
        self.db.execute('INSERT INTO monster_drops VALUES(999,100,NULL)')
        ds=[{'id':10}];attach_loot(self.db,ds)
        self.assertEqual(ds[0]['unresolved_loot'],1)
        self.assertEqual(ds[0]['loot_total'],2)
        self.assertNotIn(999,[i['id'] for i in ds[0]['loot']])
    def test_rarity_combines_with_categories(self):
        ds=[{'id':10}];attach_loot(self.db,ds,'1','include','2')
        self.assertEqual(ds[0]['loot'],[])
        attach_loot(self.db,ds,rarities='2');self.assertEqual([i['id'] for i in ds[0]['loot']],[21])

    def test_rarity_then_best_source_rate_for_every_dungeon(self):
        self.db.executescript("""
        INSERT INTO all_items VALUES(23,1,3,2,5),(24,1,3,2,6),(25,1,3,2,7),(26,1,3,NULL,8);
        INSERT INTO item_names_fr VALUES(23,'Taux faible'),(24,'Plusieurs sources'),(25,'Taux absent'),(26,'Rarete absente');
        INSERT INTO monster_drops VALUES(23,100,0.02),(24,100,0.001),(24,101,0.2),(25,100,NULL),(26,100,0.0001),(23,102,0.02);
        """)
        ds=[{'id':10},{'id':11}];attach_loot(self.db,ds)
        self.assertEqual([i['id'] for i in ds[0]['loot']],[23,21,24,25,20,26])
        self.assertEqual([i['id'] for i in ds[1]['loot']],[23,22])
        self.assertEqual(next(i for i in ds[0]['loot'] if i['id']==24)['drop_rate_raw'],0.2)
        attach_loot(self.db,ds,rarities='2')
        self.assertEqual([i['id'] for i in ds[0]['loot']],[23,21,24,25])

class WantedDungeonTests(DungeonLootTests):
    def setUp(self):
        super().setUp()
        from server import fold
        self.db.create_function('fold',1,fold)
        self.db.executescript("""
        CREATE TABLE client_dungeons(id,minimum_level);
        INSERT INTO client_dungeons VALUES(10,5),(11,10),(12,15);
        INSERT INTO translations VALUES('client_dungeons',10,'title','fr','Premier'),('client_dungeons',11,'title','fr','Second'),('client_dungeons',12,'title','fr','Vide');
        """)
    def search(self,**params):
        from server import api
        return api(self.db,'/api/search',{'kind':['dungeons'],**{k:[v] for k,v in params.items()}})
    def test_any_item_and_full_loot(self):
        result=self.search(wanted_items='20')
        self.assertEqual(result['total'],1)
        self.assertEqual([i['id'] for i in result['rows'][0]['loot']],[21,20])
        result=self.search(wanted_items='20,22')
        self.assertEqual(result['total'],2)
        self.assertEqual([d['id'] for d in result['rows']],[10,11])
    def test_selection_independent_of_display_filters(self):
        result=self.search(wanted_items='20',loot_rarities='2',loot_categories='3')
        self.assertEqual(result['total'],1)
        self.assertEqual([i['id'] for i in result['rows'][0]['loot']],[21])
        result=self.search(wanted_items='20',loot_rarities='7')
        self.assertEqual(result['total'],1)
        self.assertEqual(result['rows'][0]['loot'],[])
    def test_empty_unknown_and_pagination(self):
        self.assertEqual(self.search(wanted_items='')['total'],3)
        self.assertEqual(self.search(wanted_items='999')['total'],0)
        result=self.search(wanted_items='20,22',offset='1')
        self.assertEqual(result['total'],2)
        self.assertEqual([d['id'] for d in result['rows']],[11])
        self.assertEqual(self.search(wanted_items='20',min='6')['total'],0)
    def test_validation_and_deduplication(self):
        from dungeons import parse_wanted
        self.assertEqual(parse_wanted('20,20,22'),[20,22])
        for invalid in ['0','-1','20,','abc','2147483648',','.join(str(i) for i in range(1,102))]:
            with self.assertRaises(ValueError):self.search(wanted_items=invalid)

if __name__=='__main__' :unittest.main()
