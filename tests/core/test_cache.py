import unittest
from async_dns.core import cache, types

class TestCache(unittest.TestCase):
    def test_node(self):
        node = cache.CacheNode()
        self.assertIsNone(node.get(['com', 'fake', 'www']))
        value = node.get(['com', 'fake', 'www'], touch=True)
        self.assertIsInstance(value, cache.CacheValue)
        self.assertIs(node.get(['com', 'fake', 'www']), value)
        node.add('www.fake.com', qtype=types.A, data='8.8.8.8')
        self.assertIs(list(node.get(['com', 'fake', 'www']).get(types.A))[0].data, '8.8.8.8')
