import asyncio
import ipaddress
import unittest

from aiodnsresolver import (
    types,
    Resolver,
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
        resolve = Resolver()
        res = await resolve('www.google.com', types.A)
        self.assertEqual(res.an[0].name, 'www.google.com')
        self.assertIsInstance(ipaddress.ip_address(res.an[0].data), ipaddress.IPv4Address)

    @async_test
    async def test_aaaa_query(self):
        resolve = Resolver()
        res = await resolve('www.google.com', types.AAAA)
        self.assertEqual(res.an[0].name, 'www.google.com')
        self.assertIsInstance(ipaddress.ip_address(res.an[0].data), ipaddress.IPv6Address)

    @async_test
    async def test_a_query_not_exists(self):
        resolve = Resolver()
        res = await resolve('doenotexist.charemza.name', types.A)
        self.assertEqual(len(res.an), 0)

    @async_test
    async def test_aaaa_query_not_exists(self):
        resolve = Resolver()
        res = await resolve('doenotexist.charemza.name', types.AAAA)
        self.assertEqual(len(res.an), 0)

    @async_test
    async def test_a_query_cname(self):
        resolve = Resolver()
        res = await resolve('support.dnsimple.com', types.A)
        self.assertEqual(res.an[0].name, 'support.dnsimple.com')
        self.assertIsInstance(ipaddress.ip_address(res.an[1].data), ipaddress.IPv4Address)
