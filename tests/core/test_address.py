import unittest

from async_dns.core import Address, types


class TestAddress(unittest.TestCase):
    def test_defaults(self):
        a = Address.parse('1.1.1.1', default_protocol='udp')
        self.assertEqual(
            (a.hostinfo.hostname, a.hostinfo.port, a.ip_type, a.protocol),
            ('1.1.1.1', 53, types.A, 'udp'),
        )

    def test_ipv4(self):
        a = Address.parse('1.1.1.1:80')
        self.assertEqual(
            (a.hostinfo.hostname, a.hostinfo.port, a.ip_type, a.protocol),
            ('1.1.1.1', 80, types.A, 'udp'),
        )

    def test_ipv6(self):
        a = Address.parse('[::1]:80')
        self.assertEqual(
            (a.hostinfo.hostname, a.hostinfo.port, a.ip_type, a.protocol),
            ('::1', 80, types.AAAA, 'udp'),
        )

    def test_domain(self):
        a = Address.parse('www.google.com:443', allow_domain=True)
        self.assertEqual(
            (a.hostinfo.hostname, a.hostinfo.port, a.ip_type, a.protocol),
            ('www.google.com', 443, None, 'udp'),
        )

    def test_protocol(self):
        a = Address.parse('tcp://1.1.1.1:53')
        self.assertEqual(
            (a.hostinfo.hostname, a.hostinfo.port, a.ip_type, a.protocol),
            ('1.1.1.1', 53, types.A, 'tcp'),
        )
