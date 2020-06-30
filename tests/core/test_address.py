import unittest
from async_dns.core import Address, types

class TestAddress(unittest.TestCase):
    def test_ipv4(self):
        a1 = Address.parse('1.1.1.1:80')
        self.assertEqual(a1.host, '1.1.1.1')
        self.assertEqual(a1.port, 80)
        self.assertEqual(a1.ip_type, types.A)

    def test_ipv6(self):
        a1 = Address.parse('[::1]:80')
        self.assertEqual(a1.host, '::1')
        self.assertEqual(a1.port, 80)
        self.assertEqual(a1.ip_type, types.AAAA)

    def test_domain(self):
        a1 = Address.parse('www.google.com:443', allow_domain=True)
        self.assertEqual(a1.host, 'www.google.com')
        self.assertEqual(a1.port, 443)
        self.assertEqual(a1.ip_type, None)
