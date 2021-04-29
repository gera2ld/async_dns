import os
import unittest

from async_dns.core import parse_hosts_file

hosts = os.path.join(os.path.dirname(__file__), '../fixtures/hosts')


class TestHosts(unittest.TestCase):
    def test_hosts(self):
        result = list(parse_hosts_file(hosts))
        self.assertEqual(
            str(result),
            '[<Record type=response qtype=A name=pi3.lan ttl=-1 data=192.168.199.4>, <Record type=response qtype=A name=red.pi ttl=-1 data=192.168.199.4>]'
        )
