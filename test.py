import asyncio
import unittest

from async_dns.resolver import (
    ProxyResolver,
)
from async_dns import (
    types,
)


def async_test(func):
    def wrapper(*args, **kwargs):
        future = func(*args, **kwargs)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(future)
    return wrapper


class TestResolver(unittest.TestCase):

    @async_test
    async def test_query(self):
        resolver = ProxyResolver()
        res = await resolver.query('www.baidu.com', types.A)
        self.assertTrue(res.an)
