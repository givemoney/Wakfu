"""Read-only recipe expansion; shared demands are rounded after aggregation."""
from collections import defaultdict
from schedule import schedule_visits

def calculate_cart(db, data):
    entries = data.get('recipes')
    choices = data.get('choices', {})
    if not isinstance(entries, list) or len(entries) > 100 or not isinstance(choices, dict):
        raise ValueError('Panier invalide (100 recettes maximum).')
    def positive(n):
        if type(n) is not int or not 1 <= n <= 9999:
            raise ValueError('Quantité invalide : de 1 à 9999 fabrications.')
        return n
    def name(i):
        row = db.execute("SELECT text FROM translations WHERE entity IN ('items','job_items') AND entity_id=? AND field='title' AND language='fr' ORDER BY entity LIMIT 1", (i,)).fetchone()
        return row[0] if row else 'Nom non disponible'
    def ingredients(r):
        return list(db.execute('SELECT itemId,quantity FROM recipe_ingredients WHERE recipeId=?', (r,)))
    def recipe(r):
        row = db.execute('SELECT level,categoryId FROM recipes WHERE id=?', (r,)).fetchone()
        if not row: raise ValueError('Recette introuvable.')
        outputs = list(db.execute('SELECT productedItemId,productedItemQuantity FROM recipe_results WHERE recipeId=? ORDER BY productOrder', (r,)))
        if not outputs or any(q <= 0 for _,q in outputs) or not ingredients(r):
            raise ValueError('Recette incomplète : calcul impossible.')
        category = db.execute("SELECT text FROM translations WHERE entity='recipe_categories' AND entity_id=? AND field='title' AND language='fr'", (row[1],)).fetchone()
        return {'recipe_id': r, 'name': name(outputs[0][0]), 'level': row[0], 'job_id': row[1], 'job': category[0] if category else 'Métier non identifié', 'products': [{'id':i,'name':name(i),'quantity':q} for i,q in outputs]}
    stock_input = data.get('stock', {})
    if not isinstance(stock_input, dict) or len(stock_input) > 10000:
        raise ValueError('Stock invalide.')
    stock = {}
    for key, qty in stock_input.items():
        if not isinstance(key, str) or not key.isascii() or not key.isdigit() or int(key) <= 0 or type(qty) is not int or not 0 <= qty <= 999999:
            raise ValueError('Stock invalide : quantités entières de 0 à 999999.')
        ident = int(key)
        if not db.execute('SELECT 1 FROM recipe_ingredients WHERE itemId=? UNION SELECT 1 FROM recipe_results WHERE productedItemId=? LIMIT 1', (ident, ident)).fetchone():
            raise ValueError('Objet du stock inconnu dans les recettes.')
        stock[ident] = qty
    demand = defaultdict(int)
    basket = []
    for entry in entries:
        if not isinstance(entry, dict): raise ValueError('Panier invalide.')
        r = entry.get('recipe_id')
        if type(r) is not int or r <= 0: raise ValueError('Recette invalide.')
        count = positive(entry.get('quantity'))
        info = recipe(r); info['quantity'] = count; basket.append(info)
        for i,q in ingredients(r): demand[i] += q * count
    selected, order, marks, alternatives, candidate_yields = {}, [], {}, {}, {}
    def visit(i, depth=0):
        if depth > 200: raise ValueError("Décomposition trop profonde.")
        if marks.get(i) == 1: raise ValueError('Cycle entre recettes : calcul interrompu.')
        if marks.get(i) == 2: return
        if len(marks) >= 10000: raise ValueError('Trop de composants à décomposer.')
        marks[i] = 1
        candidates = list(db.execute('SELECT recipeId,SUM(productedItemQuantity) FROM recipe_results WHERE productedItemId=? GROUP BY recipeId ORDER BY recipeId', (i,)))
        if len(candidates)>1:
            alternatives[i] = [recipe(r) for r,q in candidates]
            candidate_yields[i] = dict(candidates)
        chosen = choices.get(str(i))
        if chosen is not None and (type(chosen) is not int or chosen not in [r for r,q in candidates]):
            raise ValueError('Choix de recette invalide.')
        if candidates:
            # The default is stable: the first recipe ID, unless the user chose one.
            r,yield_count = next((r,q) for r,q in candidates if chosen is None or r == chosen)
            if yield_count <= 0: raise ValueError('Quantité produite invalide.')
            recipe(r)
            selected[i] = (r,yield_count)
            for child,q in ingredients(r):
                if q <= 0: raise ValueError('Quantité ingrédient invalide.')
                visit(child, depth+1)
        marks[i] = 2; order.append(i)
    for i in list(demand): visit(i)
    base, pending, steps, stocked, stock_items = [], [], [], [], []
    used_stock = {}
    for i in reversed(order):
        total = demand[i]
        if not total: continue
        used = min(stock.get(i, 0), total)
        used_stock[i] = used
        qty = total - used
        stock_items.append({'id':i, 'name':name(i), 'required':total, 'stock':stock.get(i,0), 'used':used, 'missing':qty})
        if not qty:
            if i in selected:
                r, yield_count = selected[i]
                stocked.append({'id':i,'name':name(i),'quantity':total,'recipe_id':r})
            continue
        if i in selected:
            r,yield_count = selected[i]; count = (qty + yield_count - 1)//yield_count
            for child,q in ingredients(r): demand[child] += q * count
            info = recipe(r); info.update(item_id=i, required=qty, stock_used=used, quantity=count, surplus=count*yield_count-qty); steps.append(info)
        else:
            base.append({'id':i, 'name':name(i), 'quantity':qty})
    for i, qty in stock.items():
        if i not in used_stock and qty:
            stock_items.append({'id':i, 'name':name(i), 'required':0, 'stock':qty, 'used':0, 'missing':0})
    stock_items.sort(key=lambda x:x['name'].casefold())
    tree_stock = dict(used_stock)
    base.sort(key=lambda x:x['name'].casefold()); pending.sort(key=lambda x:x['name'].casefold())
    available = defaultdict(int)
    tree_nodes = 0
    def branch(i, qty):
        nonlocal tree_nodes
        tree_nodes += 1
        if tree_nodes > 20000: raise ValueError('Arbre trop volumineux.')
        used = min(tree_stock.get(i, 0), qty)
        tree_stock[i] = tree_stock.get(i, 0) - used
        node = {'id':i, 'name':name(i), 'quantity':qty, 'stock_used':used, 'children':[]}
        remaining = qty - used
        if i in selected:
            r, yield_count = selected[i]
            node['recipe_id'] = r
            reused = min(available[i], remaining)
            available[i] -= reused
            missing = remaining - reused
            count = (missing + yield_count - 1)//yield_count
            available[i] += count * yield_count - missing
            node.update(craft_count=count, reused=reused, produced=count*yield_count)
            node['children'] = [branch(child,q*count) for child,q in sorted(ingredients(r), key=lambda row: row[0] not in selected)] if count else []
        return node
    def tree_ingredients(r):
        return sorted(ingredients(r), key=lambda row: row[0] not in selected)
    trees = []
    for entry in basket:
        trees.append({'recipe_id':entry['recipe_id'], 'name':entry['name'],
                      'quantity':entry['quantity'], 'products':entry['products'],
                      'children':[branch(i,q*entry['quantity']) for i,q in tree_ingredients(entry['recipe_id'])]})
    grouped = {}
    roots = {entry['recipe_id'] for entry in basket}
    for entry in steps + basket:
        rid = entry['recipe_id']
        if rid not in grouped:
            grouped[rid] = recipe(rid)
            grouped[rid].update(quantity=0, final=rid in roots)
        grouped[rid]['quantity'] += entry['quantity']
    dependencies = {r:{selected[i][0] for i,q in ingredients(r) if i in selected and selected[i][0] in grouped} for r in grouped}
    visits, schedule_optimal = schedule_visits(grouped, dependencies)
    plan = []
    for passage in visits:
        for rid in passage['recipe_ids']:
            entry = grouped[rid]
            entry['visit'] = passage['number']
            entry['ingredients'] = [{'id':i,'name':name(i),'quantity':q*entry['quantity']} for i,q in ingredients(rid)]
            entry['dependencies'] = sorted(dependencies[rid])
            entry['products'] = [dict(product,quantity=product['quantity']*entry['quantity']) for product in entry['products']]
            plan.append(entry)
    recipe_choices = []
    for i, opts in alternatives.items():
        used = used_stock.get(i, 0)
        missing = demand[i] - used
        if missing <= 0:
            continue
        scaled_options = []
        for opt in opts:
            rid = opt['recipe_id']
            yield_count = candidate_yields[i][rid]
            count = (missing + yield_count - 1) // yield_count
            scaled_options.append(dict(
                opt, yield_count=yield_count, craft_count=count,
                surplus=count * yield_count - missing,
                ingredients=[{'id':child, 'name':name(child), 'quantity':qty * count}
                             for child, qty in ingredients(rid)]))
        recipe_choices.append({
            'id':i, 'name':name(i), 'quantity':missing, 'stock_used':used,
            'selected_recipe_id':selected[i][0],
            'selection_default':choices.get(str(i)) is None,
            'options':scaled_options})
    return {'basket':basket, 'base':base, 'pending':pending, 'steps':steps, 'complete':not pending, 'trees':trees, 'plan':plan, 'visits':visits, 'schedule_optimal':schedule_optimal, 'stock_items':stock_items, 'stocked':stocked, 'recipe_choices':recipe_choices}
