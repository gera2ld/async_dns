import asyncio
import re
import unittest

from aiogethostbyname import (
    Resolver,
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
    async def test_a_query(self):
        resolver = Resolver()
        res = await resolver.query('www.google.com', types.A)
        self.assertEqual(res.an[0].name, 'www.google.com')
        self.assertTrue(re.match( r'\d+\.\d+\.\d+\.\d+', res.an[0].data))
