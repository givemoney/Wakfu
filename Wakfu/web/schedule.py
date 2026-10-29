"""Minimize artisan visits under recipe precedence and unlimited storage."""
from heapq import heappop, heappush
from time import monotonic


def schedule_visits(grouped, dependencies, max_states=30000, seconds=2):
    ids = sorted(grouped)
    bits = {rid: 1 << i for i, rid in enumerate(ids)}
    full = (1 << len(ids)) - 1
    needs = {rid: sum(bits[d] for d in dependencies[rid]) for rid in ids}
    jobs = {}
    for rid in ids:
        job = grouped[rid].get('job_id', grouped[rid]['job'])
        jobs.setdefault(job, []).append(rid)
    job_order = sorted(jobs, key=lambda j: (grouped[jobs[j][0]]['job'], str(j)))
    for job in jobs:
        jobs[job].sort(key=lambda r: (grouped[r].get('final', False), grouped[r]['level'], r))

    def visit(state, job):
        result = []
        while True:
            ready = [r for r in jobs[job] if not state & bits[r] and needs[r] & state == needs[r]]
            if not ready:
                return state, result
            for rid in ready:
                state |= bits[rid]
                result.append(rid)

    def remaining_jobs(state):
        return sum(any(not state & bits[r] for r in jobs[j]) for j in jobs)

    # Completing every currently possible recipe at a visited artisan cannot
    # increase later visits: prerequisites only become available, never expire.
    state, incumbent = 0, []
    while state != full:
        options = [(j, *visit(state, j)) for j in job_order]
        options = [o for o in options if o[1] != state]
        if not options:
            raise ValueError('Cycle dans le plan de fabrication.')
        job, state, recipes = min(options, key=lambda o: (remaining_jobs(o[1]), -len(o[2]), job_order.index(o[0])))
        incumbent.append((job, recipes))
    optimal = len(incumbent) == len(jobs)
    explored = 0
    if not optimal:
        deadline = monotonic() + seconds
        queue = [(len(jobs), 0, 0)]
        costs, parents = {0: 0}, {}
        while queue and explored < max_states and monotonic() < deadline:
            lower, cost, state = heappop(queue)
            if cost != costs.get(state):
                continue
            if lower >= len(incumbent):
                optimal = True
                break
            if state == full:
                path = []
                while state:
                    previous, job, recipes = parents[state]
                    path.append((job, recipes))
                    state = previous
                incumbent = list(reversed(path))
                optimal = True
                break
            explored += 1
            for job in job_order:
                next_state, recipes = visit(state, job)
                next_cost = cost + 1
                if next_state == state or next_cost >= costs.get(next_state, float('inf')):
                    continue
                bound = next_cost + remaining_jobs(next_state)
                if bound >= len(incumbent):
                    continue
                costs[next_state] = next_cost
                parents[next_state] = (state, job, recipes)
                heappush(queue, (bound, next_cost, next_state))
        else:
            optimal = not queue
    visits = [{'number': n, 'job': grouped[recipes[0]]['job'], 'recipe_ids': recipes}
              for n, (_, recipes) in enumerate(incumbent, 1)]
    return visits, optimal
