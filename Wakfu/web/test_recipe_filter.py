import sqlite3
import unittest
from recipe_filter import allowed_recipes

class ExclusionTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.executescript("CREATE TABLE recipe_ingredients(recipeId,itemId,quantity); CREATE TABLE recipe_results(recipeId,productedItemId,productedItemQuantity); INSERT INTO recipe_results VALUES(1,100,1),(2,200,1),(3,200,1),(4,400,1),(5,500,1); INSERT INTO recipe_ingredients VALUES(1,200,1),(2,300,1),(3,301,1),(4,500,1),(5,400,1);")
    def tearDown(self): self.db.close()
    def test_alternative(self): self.assertIn(1,allowed_recipes(self.db,{300}))
    def test_all_alternatives_excluded(self): self.assertNotIn(1,allowed_recipes(self.db,{300,301}))
    def test_intermediate_itself_excluded(self): self.assertNotIn(1,allowed_recipes(self.db,{200}))
    def test_cycle(self): self.assertFalse({4,5}&allowed_recipes(self.db,{300}))
if __name__=='__main__': unittest.main()
