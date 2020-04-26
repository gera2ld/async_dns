import unittest
from async_dns.core import rand

class TestRand(unittest.TestCase):
    def test_rand(self):
        r = rand.RandId(1, 10)
        for _ in range(10):
            r.get()
        self.assertEqual(r.data, [])
        for i in range(10):
            r.put(i + 1)
        self.assertEqual(r.data, [(1, 10)])
