import asyncio
import unittest

from async_dns.resolver import (
	ProxyResolver,
)
from async_dns import (
	types,
)


class TestResolver(unittest.TestCase):

    def test_query(self):
        loop = asyncio.get_event_loop()
        resolver = ProxyResolver()
        res = loop.run_until_complete(resolver.query('www.baidu.com', types.A))
        self.assertTrue(res.an)
