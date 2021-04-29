import unittest

from async_dns.core import types
from async_dns.resolver import ProxyResolver
from util import async_test


class TestResolver(unittest.TestCase):
    @async_test
    async def test_query(self):
        resolver = ProxyResolver()
        res, cache1 = await resolver.query('www.baidu.com', types.A)
        _, cache2 = await resolver.query('www.baidu.com', types.A)
        self.assertTrue(res.an)
        self.assertFalse(cache1)
        self.assertTrue(cache2)
