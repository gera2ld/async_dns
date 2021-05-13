from unittest import TestCase

from async_dns.core import Address, types
from async_dns.request import clean
from async_dns.resolver import DNSClient

from ..util import async_test


class TestClient(TestCase):
    def tearDown(self):
        clean()

    @async_test
    async def test_client(self):
        dns = DNSClient()
        res = await dns.query('gmail.com', types.A, Address.parse('8.8.8.8'))
        self.assertEqual(res.qd[0].name, 'gmail.com')
