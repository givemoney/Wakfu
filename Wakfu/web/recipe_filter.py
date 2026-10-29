"""Ingredient exclusion, including alternative intermediate recipes."""
from collections import defaultdict, deque


def allowed_recipes(db, excluded):
    ingredients = defaultdict(set)
    products = defaultdict(set)
    for rid, item in db.execute('SELECT recipeId,itemId FROM recipe_ingredients WHERE quantity>0'):
        ingredients[rid].add(item)
    for rid, item in db.execute('SELECT recipeId,productedItemId FROM recipe_results WHERE productedItemQuantity>0'):
        products[rid].add(item)
    producers = {item for items in products.values() for item in items}
    consumers = defaultdict(set)
    remaining = {}
    for rid, items in ingredients.items():
        if rid not in products:
            continue
        remaining[rid] = len(items)
        for item in items:
            consumers[item].add(rid)
    # Least fixed point: alternatives are OR, ingredients are AND. Cycles do
    # not count as a way to manufacture a component without a finite base.
    queue = deque(item for item in consumers if item not in producers and item not in excluded)
    safe_items = set(queue)
    safe_recipes = set()
    while queue:
        item = queue.popleft()
        for rid in consumers[item]:
            remaining[rid] -= 1
            if remaining[rid] == 0:
                safe_recipes.add(rid)
                for output in products[rid]:
                    if output not in excluded and output not in safe_items:
                        safe_items.add(output)
                        queue.append(output)
    return safe_recipes
