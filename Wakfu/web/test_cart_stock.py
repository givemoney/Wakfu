import sqlite3
import unittest
from cart import calculate_cart

class StockTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.executescript("""CREATE TABLE recipes(id,level,categoryId);
        CREATE TABLE recipe_ingredients(recipeId,itemId,quantity);
        CREATE TABLE recipe_results(recipeId,productedItemId,productedItemQuantity,productOrder);
        CREATE TABLE translations(entity,entity_id,field,language,text);
        INSERT INTO recipes VALUES(1,10,1),(2,10,1),(3,5,2),(4,5,3);
        INSERT INTO recipe_results VALUES(1,100,1,0),(2,101,1,0),(3,200,1,0),(4,300,1,0);
        INSERT INTO recipe_ingredients VALUES(1,200,1),(1,300,1),(2,200,1),(3,400,2),(4,400,3);""")
    def tearDown(self): self.db.close()
    def calc(self, stock=None):
        return calculate_cart(self.db,{'recipes':[{'recipe_id':1,'quantity':1},{'recipe_id':2,'quantity':1}], 'stock':stock or {}})
    def test_no_stock_preserves_totals(self):
        d=self.calc()
        self.assertEqual(d['base'],[{'id':400,'name':'Nom non disponible','quantity':7}])
        self.assertEqual({r['recipe_id']:r['quantity'] for r in d['plan']},{1:1,2:1,3:2,4:1})
    def test_shared_stock_consumed_once(self):
        d=self.calc({'200':1})
        self.assertEqual(d['base'][0]['quantity'],5)
        self.assertEqual(next(r for r in d['steps'] if r['item_id']==200)['quantity'],1)
        self.assertEqual(next(r for r in d['stock_items'] if r['id']==200)['used'],1)
        def nodes(ns):
            for n in ns:
                yield n
                yield from nodes(n['children'])
        self.assertEqual(sum(n['stock_used'] for t in d['trees'] for n in nodes(t['children']) if n['id']==200),1)
    def test_parent_stock_prunes_children_before_using_raw_stock(self):
        d=self.calc({'200':1,'300':1,'400':1})
        self.assertEqual(d['base'][0]['quantity'],1)
        self.assertNotIn(4,{r['recipe_id'] for r in d['plan']})
        self.assertEqual(d['stocked'][0]['id'],300)
        self.assertNotIn(4,{rid for v in d['visits'] for rid in v['recipe_ids']})
    def test_excess_stock_not_reused(self):
        d=self.calc({'200':50})
        s=next(r for r in d['stock_items'] if r['id']==200)
        self.assertEqual((s['stock'],s['used'],s['missing']),(50,2,0))
        self.assertEqual(d['base'][0]['quantity'],3)
    def test_round_after_stock_and_aggregation(self):
        self.db.execute('UPDATE recipe_results SET productedItemQuantity=2 WHERE recipeId=3')
        d=self.calc({'200':1})
        self.assertEqual(d['base'][0]['quantity'],5)
        self.assertEqual(next(r for r in d['steps'] if r['item_id']==200)['surplus'],1)
    def test_stock_resolves_ambiguous_component(self):
        self.db.executescript('INSERT INTO recipes VALUES(5,1,2); INSERT INTO recipe_results VALUES(5,200,1,0); INSERT INTO recipe_ingredients VALUES(5,400,8);')
        self.assertTrue(self.calc()['complete'])
        self.assertTrue(self.calc({'200':2})['complete'])
    def test_alternatives_visible_after_selection(self):
        self.db.executescript('INSERT INTO recipes VALUES(5,1,2); INSERT INTO recipe_results VALUES(5,200,1,0); INSERT INTO recipe_ingredients VALUES(5,400,8);')
        d=calculate_cart(self.db,{'recipes':[{'recipe_id':1,'quantity':1}], 'choices':{'200':3}})
        self.assertTrue(d['complete'])
        self.assertEqual(d['recipe_choices'][0]['id'],200)
        self.assertEqual({r['recipe_id'] for r in d['recipe_choices'][0]['options']},{3,5})
    def test_invalid_stock_rejected(self):
        for stock in [{'200':-1},{'200':True},{'200':1.5},{'99999':1},[],{'200':1000000}]:
            with self.subTest(stock=stock), self.assertRaises(ValueError):
                calculate_cart(self.db,{'recipes':[{'recipe_id':1,'quantity':1}], 'stock':stock})

if __name__=='__main__': unittest.main()
