import unittest

from async_dns.core.record import DNSMessage


class TestRecord(unittest.TestCase):
    def test_record(self):
        msg = DNSMessage.parse(
            b'\xe2@\x01 \x00\x01\x00\x00\x00\x00\x00\x01\x03www\x05baidu\x03com\x00\x00\x01\x00\x01\x00\x00)\x10\x00\x00\x00\x00\x00\x00\x00'
        )
        self.assertEqual(msg.qd[0].name, 'www.baidu.com')
