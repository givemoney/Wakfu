"""Alternative recipes must produce a complete, stock-aware crafting plan."""
import sqlite3
import unittest

from cart import calculate_cart


class RecipeChoiceTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.executescript("""
            CREATE TABLE recipes(id,level,categoryId);
            CREATE TABLE recipe_ingredients(recipeId,itemId,quantity);
            CREATE TABLE recipe_results(recipeId,productedItemId,productedItemQuantity,productOrder);
            CREATE TABLE translations(entity,entity_id,field,language,text);
            INSERT INTO recipes VALUES
                (1,10,1),(2,10,2),(10,5,3),(20,5,4),(30,5,5),(40,5,6);
            INSERT INTO recipe_results VALUES
                (1,100,1,0),(2,101,1,0),(10,200,2,0),(20,200,1,0),
                (30,300,1,0),(40,300,3,0);
            INSERT INTO recipe_ingredients VALUES
                (1,200,3),(1,300,2),(2,200,2),(10,400,3),(10,401,1),
                (20,500,7),(30,600,2),(40,700,5);
        """)

    def tearDown(self):
        self.db.close()

    def calculate(self, choices=None, stock=None):
        return calculate_cart(self.db, {
            'recipes': [{'recipe_id': 1, 'quantity': 1},
                        {'recipe_id': 2, 'quantity': 1}],
            'choices': choices or {}, 'stock': stock or {},
        })

    @staticmethod
    def quantities(rows):
        return {row['id']: row['quantity'] for row in rows}

    @staticmethod
    def choices(result):
        return {row['id']: row for row in result['recipe_choices']}

    def test_first_recipe_is_selected_in_stable_order_and_plan_is_complete(self):
        # Insertion order must not change the default selection.
        self.db.execute('DELETE FROM recipe_results WHERE recipeId=10')
        self.db.execute('INSERT INTO recipe_results VALUES(10,200,2,0)')
        result = self.calculate()
        self.assertTrue(result['complete'])
        self.assertEqual(result['pending'], [])
        self.assertEqual(self.quantities(result['base']), {400: 9, 401: 3, 600: 4})
        choice = self.choices(result)[200]
        self.assertEqual(choice['selected_recipe_id'], 10)
        self.assertTrue(choice['selection_default'])
        self.assertEqual([option['recipe_id'] for option in choice['options']], [10, 20])
        self.assertEqual({step['recipe_id']: step['quantity'] for step in result['plan']},
                         {1: 1, 2: 1, 10: 3, 30: 2})

    def test_explicit_selection_changes_only_its_requirements(self):
        result = self.calculate(choices={'200': 20})
        choice = self.choices(result)[200]
        self.assertEqual(choice['selected_recipe_id'], 20)
        self.assertFalse(choice['selection_default'])
        self.assertEqual(self.quantities(result['base']), {500: 35, 600: 4})
        self.assertEqual({step['recipe_id']: step['quantity'] for step in result['plan']},
                         {1: 1, 2: 1, 20: 5, 30: 2})
        self.assertTrue(self.choices(result)[300]['selection_default'])

    def test_option_totals_use_shared_demand_after_partial_stock(self):
        result = self.calculate(stock={'200': 2, '300': 1})
        choice = self.choices(result)[200]
        self.assertEqual((choice['quantity'], choice['stock_used']), (3, 2))
        options = {option['recipe_id']: option for option in choice['options']}
        self.assertEqual((options[10]['yield_count'], options[10]['craft_count'],
                          options[10]['surplus']), (2, 2, 1))
        self.assertEqual(self.quantities(options[10]['ingredients']), {400: 6, 401: 2})
        self.assertEqual((options[20]['craft_count'], options[20]['surplus']), (3, 0))
        self.assertEqual(self.quantities(options[20]['ingredients']), {500: 21})
        self.assertEqual(self.quantities(result['base']), {400: 6, 401: 2, 600: 2})
        stock = {row['id']: row for row in result['stock_items']}
        self.assertEqual((stock[200]['required'], stock[200]['used'], stock[200]['missing']),
                         (5, 2, 3))

    def test_fully_stocked_components_have_no_choice_or_descendant_requirements(self):
        result = self.calculate(stock={'200': 5, '300': 2})
        self.assertTrue(result['complete'])
        self.assertEqual(result['recipe_choices'], [])
        self.assertEqual(result['base'], [])
        self.assertEqual(result['steps'], [])
        self.assertEqual({step['recipe_id'] for step in result['plan']}, {1, 2})
        self.assertFalse(any(row['id'] in {400, 401, 500, 600, 700} and row['required']
                             for row in result['stock_items']))

    def test_multiple_ambiguous_components_keep_independent_explicit_choices(self):
        result = self.calculate(choices={'200': 20, '300': 40})
        choices = self.choices(result)
        self.assertEqual({ident: row['selected_recipe_id'] for ident, row in choices.items()},
                         {200: 20, 300: 40})
        self.assertTrue(all(not row['selection_default'] for row in choices.values()))
        self.assertEqual(self.quantities(result['base']), {500: 35, 700: 5})
        second_option = next(option for option in choices[300]['options']
                             if option['recipe_id'] == 40)
        self.assertEqual((second_option['craft_count'], second_option['surplus']), (1, 1))

    def test_selected_intermediate_crafts_precede_every_dependent_final_craft(self):
        result = self.calculate()
        positions = {row['recipe_id']: index for index, row in enumerate(result['plan'])}
        self.assertLess(positions[10], positions[1])
        self.assertLess(positions[10], positions[2])
        self.assertLess(positions[30], positions[1])
        dependencies = {row['recipe_id']: set(row['dependencies']) for row in result['plan']}
        self.assertEqual(dependencies[1], {10, 30})
        self.assertEqual(dependencies[2], {10})
        self.assertEqual(len([row for row in result['plan'] if row['recipe_id'] == 10]), 1)

    def test_cycle_in_default_recipe_is_still_rejected(self):
        self.db.executescript("""
            INSERT INTO recipes VALUES(9,1,7);
            INSERT INTO recipe_results VALUES(9,400,1,0);
            INSERT INTO recipe_ingredients VALUES(9,200,1);
        """)
        with self.assertRaisesRegex(ValueError, 'Cycle'):
            self.calculate()
        # Selecting the other alternative avoids that cycle entirely.
        self.assertTrue(self.calculate(choices={'200': 20})['complete'])


if __name__ == '__main__':
    unittest.main()
