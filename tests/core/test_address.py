import unittest
from async_dns.core import Address, types

class TestAddress(unittest.TestCase):
    def test_ipv4(self):
        a1 = Address('1.1.1.1', 80)
        a2 = Address('2.2.2.2:81')
        self.assertEqual(a1.host, '1.1.1.1')
        self.assertEqual(a1.port, 80)
        self.assertEqual(a1.ip_type, types.A)
        self.assertEqual(a2.host, '2.2.2.2')
        self.assertEqual(a2.port, 81)
        self.assertEqual(a2.ip_type, types.A)

    def test_ipv6(self):
        a1 = Address('::1', 80)
        a2 = Address('[::1]:81')
        self.assertEqual(a1.host, '::1')
        self.assertEqual(a1.port, 80)
        self.assertEqual(a1.ip_type, types.AAAA)
        self.assertEqual(a2.host, '::1')
        self.assertEqual(a2.port, 81)
        self.assertEqual(a2.ip_type, types.AAAA)

    def test_domain(self):
        a1 = Address('www.google.com', 80, allow_domain=True)
        a2 = Address('www.baidu.com:443', allow_domain=True)
        self.assertEqual(a1.host, 'www.google.com')
        self.assertEqual(a1.port, 80)
        self.assertEqual(a1.ip_type, None)
        self.assertEqual(a2.host, 'www.baidu.com')
        self.assertEqual(a2.port, 443)
        self.assertEqual(a2.ip_type, None)
