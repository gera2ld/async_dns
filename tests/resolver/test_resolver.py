import unittest
from unittest.mock import patch

from async_dns.core import DNSMessage, Record, types
from async_dns.resolver import ProxyResolver

from ..util import async_test


class TestResolver(unittest.TestCase):
    def _make_response(self, name='www.baidu.com', qtype=types.A):
        msg = DNSMessage(qid=0)
        msg.ra = 1
        msg.r = 0
        msg.an = [Record(name=name, qtype=qtype, ttl=60)]
        return msg

    @async_test
    async def test_query_returns_a_message_on_success(self):
        resolver = ProxyResolver()
        fake_response = self._make_response()
        calls = []

        async def fake_request(*args, **kwargs):
            calls.append((args, kwargs))
            return fake_response

        with patch.object(resolver, 'request', new=fake_request):
            res, from_cache = await resolver.query('www.baidu.com', types.A)

        self.assertTrue(res.an)
        self.assertFalse(from_cache)
        self.assertEqual(len(calls), 1)

    @async_test
    async def test_query_uses_cached_results_for_repeat_lookups(self):
        resolver = ProxyResolver()
        fake_response = self._make_response()
        calls = []

        async def fake_request(*args, **kwargs):
            calls.append((args, kwargs))
            return fake_response

        with patch.object(resolver, 'request', new=fake_request):
            first_res, first_from_cache = await resolver.query('www.baidu.com', types.A)
            second_res, second_from_cache = await resolver.query('www.baidu.com', types.A)

        self.assertTrue(first_res.an)
        self.assertFalse(first_from_cache)
        self.assertTrue(second_res.an)
        self.assertTrue(second_from_cache)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(list(resolver.cache.query('www.baidu.com', types.A))), 1)
