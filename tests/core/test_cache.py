import unittest

from async_dns.core import cache, types


class TestCache(unittest.TestCase):
    def test_node(self):
        node = cache.CacheNode()
        self.assertIsNone(node.get('www.fake.com'))
        value = node.get('www.fake.com', touch=True)
        self.assertIsInstance(value, cache.CacheValue)
        self.assertIs(node.get('www.fake.com'), value)
        node.add('www.fake.com', qtype=types.A, data=('8.8.8.8', ))
        self.assertIs(
            list(node.get('www.fake.com').get(types.A))[0].data.data,
            '8.8.8.8')
