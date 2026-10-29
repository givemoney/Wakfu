"""Run: python -B -m unittest discover -s web -p test_schedule.py"""
import itertools
import random
import unittest
from schedule import schedule_visits

class ScheduleTests(unittest.TestCase):
    def test_forced_return(self):
        nodes = {i: {'job': job, 'level': 1} for i, job in enumerate('ABA')}
        visits, optimal = schedule_visits(nodes, {0:set(), 1:{0}, 2:{1}})
        self.assertTrue(optimal)
        self.assertEqual([v['job'] for v in visits], ['A','B','A'])

    def test_exhaustive_orders(self):
        rng = random.Random(7)
        for n in range(1, 7):
            for sample in range(15):
                nodes = {r: {'job': str(rng.randrange(3)), 'level':1} for r in range(n)}
                deps = {r:{d for d in range(r) if rng.random()<.23} for r in range(n)}
                best = n
                for order in itertools.permutations(range(n)):
                    done, last, cost = set(), None, 0
                    for r in order:
                        if not deps[r] <= done: break
                        job = nodes[r]['job']
                        cost += job != last
                        last = job
                        done.add(r)
                    else: best = min(best, cost)
                visits, optimal = schedule_visits(nodes, deps)
                self.assertTrue(optimal)
                self.assertEqual(len(visits), best)

    def test_budget_reports_unproven(self):
        nodes = {i: {'job':job, 'level':1} for i,job in enumerate('ABA')}
        visits, optimal = schedule_visits(nodes, {0:set(),1:{0},2:{1}}, max_states=0)
        self.assertFalse(optimal)
        self.assertEqual(len(visits),3)

if __name__ == '__main__': unittest.main()
