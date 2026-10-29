import json,pathlib,sqlite3,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'updater'))
from geography import territory_at,enrich_world

class TerritoryLookup(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.executescript('CREATE TABLE geography_worlds(id,name,region_id,region_name); CREATE TABLE geography_territories(id,world_id,name); CREATE TABLE arrays(entity,entity_id,field,value);')
        self.db.execute('INSERT INTO geography_territories VALUES(1,458,"Zone")')
        self.db.execute('INSERT INTO arrays VALUES("geography_territories",1,"cells","-65536")')
    def tearDown(self):self.db.close()
    def test_negative_coordinates_use_floor_and_correct_xy_order(self):
        self.assertEqual(territory_at(self.db,458,-1,0),1)
        self.assertIsNone(territory_at(self.db,458,0,-1))
    def test_overlapping_territories_are_not_guessed(self):
        self.db.execute('INSERT INTO geography_territories VALUES(2,458,"Other")')
        self.db.execute('INSERT INTO arrays VALUES("geography_territories",2,"cells","-65536")')
        self.assertIsNone(territory_at(self.db,458,-1,0))
    def test_unknown_world_not_assigned_an_invented_region(self):
        self.assertEqual(enrich_world(self.db,999999),{})

class OfficialRelations(unittest.TestCase):
    def setUp(self):self.db=sqlite3.connect('file:'+str(pathlib.Path(__file__).resolve().parents[1]/'wakfu.sqlite').replace('\\','/')+'?mode=ro',uri=True)
    def tearDown(self):self.db.close()
    def test_every_entrance_uses_the_dungeon_link_list(self):
        mismatches=self.db.execute("SELECT count(*) FROM dungeon_entrances e JOIN map_points p ON p.id=e.point_id AND p.world_id=e.world_id WHERE NOT EXISTS (SELECT 1 FROM source_records r,json_each(r.payload,'$.definition.binary.field_8') links WHERE r.dataset='client_dungeons' AND json_extract(r.payload,'$.definition.id')=e.dungeon_id AND links.value=p.link_id)").fetchone()[0]
        self.assertEqual(mismatches,0)
        self.assertGreater(self.db.execute('SELECT COUNT(*) FROM dungeon_entrances').fetchone()[0],100)
    def test_all_accepted_entrances_have_consistent_regions(self):
        self.assertEqual(self.db.execute('SELECT count(*) FROM dungeon_entrances e JOIN client_dungeons d ON d.id=e.dungeon_id JOIN geography_worlds w ON w.id=d.world_map_id JOIN geography_worlds entry ON entry.id=e.world_id WHERE w.region_id<>entry.region_id').fetchone()[0],0)
    def test_global_territory_coverage_not_two_item_overrides(self):
        self.assertGreater(self.db.execute('SELECT COUNT(DISTINCT monster_id) FROM monster_territory_hints').fetchone()[0],650)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM geography_worlds').fetchone()[0],720)

if __name__=='__main__':unittest.main()
