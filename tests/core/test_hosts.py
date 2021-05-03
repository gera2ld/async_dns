import os
import unittest

from async_dns.core import parse_hosts_file

hosts = os.path.join(os.path.dirname(__file__), '../fixtures/hosts')


class TestHosts(unittest.TestCase):
    def test_hosts(self):
        result = list(parse_hosts_file(hosts))
        self.assertEqual(
            result,
            [('pi3.lan', 1, ('192.168.199.4', )),
             ('red.pi', 1, ('192.168.199.4', ))],
        )
