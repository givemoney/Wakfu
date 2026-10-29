import json
import sqlite3
import unittest
from unittest.mock import patch
import locations
from server import fold

class HarvestLocationsTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row;self.db.create_function('fold',1,fold)
        self.db.executescript('''
        CREATE TABLE geography_worlds(id,name);INSERT INTO geography_worlds VALUES(1,'Astrub'),(2,'Donjon');
        CREATE TABLE geography_territories(id,name,world_id);INSERT INTO geography_territories VALUES(5,'Champs',1),(6,'Salle du donjon',2);
        CREATE TABLE client_dungeons(world_map_id);INSERT INTO client_dungeons VALUES(1);
        CREATE TABLE arrays(entity,field,value);INSERT INTO arrays VALUES('client_dungeons','instance_ids','2');
        CREATE TABLE resources(id,resourceType);INSERT INTO resources VALUES(1,20),(2,7),(3,1),(4,2),(5,10);
        CREATE TABLE harvest_actions(resourceId,collectItemId,collectLootListId,skillLevelRequired,resourceNextIndex);
        INSERT INTO harvest_actions VALUES(1,101,0,10,0),(2,102,0,15,0),(3,103,0,20,0),(3,106,0,20,2),(3,107,0,20,3),(4,104,0,0,0),(5,105,0,5,0),(1,101,0,10,0);
        CREATE TABLE all_items(id,type_id);INSERT INTO all_items VALUES(101,308),(102,281),(103,306),(104,309),(105,313),(106,306),(107,309),(108,281);
        CREATE TABLE item_names_fr(id,name);INSERT INTO item_names_fr VALUES(101,'Poisson'),(102,'Minerai'),(103,'Bois'),(104,'Blé'),(105,'Fleur'),(106,'Bouture'),(107,'Fruit'),(108,'Butin de monstre');
        CREATE TABLE harvest_loots(itemId,listId,itemIsLootList);
        INSERT INTO harvest_loots VALUES(106,44,0);
        UPDATE harvest_actions SET collectLootListId=44 WHERE resourceId=3 AND resourceNextIndex=0;
        ''')
        self.reference={'links':[{'territory_id':t,'world_id':w,'resource_id':r} for t,w in [(5,1),(6,2)] for r in range(1,6)]}
        self.mock=patch.object(locations,'load_reference',return_value=self.reference);self.mock.start()
    def tearDown(self):self.mock.stop();self.db.close()
    def test_only_five_categories_and_no_dungeons_or_monster_drops(self):
        result=locations.search(self.db,{})
        self.assertEqual([r['id'] for r in result['rows']],[5])
        result=locations.detail(self.db,{'id':['5']})
        self.assertEqual({c['category_key'] for c in result['components']},{'fish','ores','wood','crops','herbs'})
        self.assertEqual({c['id'] for c in result['components']},{101,102,103,104,105})
        with self.assertRaises(ValueError):locations.detail(self.db,{'id':['6']})
    def test_wood_excludes_cuttings_and_fruit(self):
        result=locations.detail(self.db,{'id':['5']})
        self.assertEqual([c['id'] for c in result['components'] if c['category_key']=='wood'],[103])
    def test_deduplication_and_gathering_levels(self):
        zone=locations.search(self.db,{})['rows'][0]
        self.assertEqual(zone['component_count'],5)
        self.assertEqual((zone['level'],zone['level_max']),(0,20))
        self.assertEqual(locations.search(self.db,{'min':['1']})['total'],0)
    def test_search_by_harvest_name_and_accent(self):
        self.assertEqual(locations.search(self.db,{'q':['ble']})['total'],1)
        self.assertEqual(locations.search(self.db,{'q':['Bouture']})['total'],0)
    def test_missing_matching_reference_is_not_guessed(self):
        with patch.object(locations,'load_reference',return_value=None):
            result=locations.search(self.db,{})
        self.assertEqual(result['total'],0)
        self.assertTrue(result['coverage_message'])

if __name__=='__main__':unittest.main()
