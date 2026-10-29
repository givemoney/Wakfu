import json
import sqlite3
import unittest
from item_stats import formatted_effects,render_template,values

class ItemStatsTests(unittest.TestCase):
    def test_baguette_missing_mastery_and_two_damage_values(self):
        template='[#charac DMG_IN_PERCENT] {[~3]?[#1] Maîtrise [#3]:[#1] Maîtrise sur [#2] élément{[>2]?s:}}'
        self.assertEqual(render_template(template,values([26,0,1,0],72)),'26 Maîtrise sur 1 élément')
        self.assertEqual(values([4,.335],72)[0][0],28)
        self.assertEqual(values([5,.41875002],72)[0][0],35)
    def test_nested_plural_and_parameter_presence(self):
        self.assertEqual(render_template('{[~3]?spécifique:[#1] sur [#2] élément{[>2]?s:}}',values([26,0,3,0],72)),'26 sur 3 éléments')
        self.assertEqual(render_template('{[+1]?positif:négatif}',values([-2,0],1)),'négatif')
    def test_reference_client_rounding(self):
        self.assertEqual(values([0,.3],10)[0][0],3)
        self.assertEqual(values([0,-.3],10)[0][0],-3)
        self.assertEqual(values([10,-.335],3)[0][0],9)
    def test_no_template_execution(self):
        self.assertEqual(render_template('${alert(1)}',[]),'${alert(1)}')
    def test_damage_template_does_not_show_absent_percentage_conditions(self):
        template='Dommage [el6] : [#1]{[+3]? % des PV:}{[+3]?{[1=3]? max: courants}:}'
        self.assertEqual(render_template(template,values([4,.335],72)),'Dommage Lumière : 28')
    def test_every_effect_is_returned_with_its_kind(self):
        db=sqlite3.connect(':memory:')
        db.execute('CREATE TABLE actions(id,effect)');db.execute("INSERT INTO actions VALUES(330,'Groupe d’effets')")
        effects=[{'action_id':20,'description':'[#1] PV','payload':json.dumps({'params':[60,0]}),'kind':'equipEffects'},
                 {'action_id':330,'description':None,'payload':json.dumps({'params':[]}),'kind':'useEffects'}]
        data=formatted_effects(db,effects,72)
        self.assertEqual(len(data),2);self.assertEqual(data[0]['text'],'60 PV');self.assertEqual(data[1]['kind'],'useEffects');db.close()

if __name__=='__main__':unittest.main()
