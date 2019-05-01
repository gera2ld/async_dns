import unittest
from async_dns.core import utils

class TestUtils(unittest.TestCase):
    def test_load_message(self):
        data = (
            b'D7\x81\x80\x00\x01\x00\x01\x00\x00\x00\x00\x03'
            b'www\x06google\x03com\x00\x00\x01\x00\x01\xc0\x0c'
            b'\x00\x01\x00\x01\x00\x00\t\xb5\x00\x04\xcbb\x07A'
        )
        self.assertEqual(utils.load_message(data, 12), (28, 'www.google.com'))
        self.assertEqual(utils.load_message(data, 32), (34, 'www.google.com'))

    def test_pack_message(self):
        names = {}
        self.assertEqual(utils.pack_message('a.b.c', names, 0), b'\x01a\x01b\x01c\x00')
        self.assertEqual(utils.pack_message('b.c', names, 10), b'\xc0\x02')
        self.assertEqual(utils.pack_message('b.c.d', names, 12), b'\x01b\x01c\x01d\x00')
        self.assertEqual(names, {'a.b.c': 0, 'b.c': 2, 'c': 4, 'b.c.d': 12, 'c.d': 14, 'd': 16})

    def test_pack_string(self):
        self.assertEqual(utils.pack_string('hello'), b'\5hello')
        self.assertEqual(utils.pack_string('hello', '!H'), b'\0\5hello')

    def test_get_bits(self):
        self.assertEqual(utils.get_bits(0b11110000, 4), (0, 0b1111))
        self.assertEqual(utils.get_bits(0b11110000, 2), (0, 0b111100))
        self.assertEqual(utils.get_bits(0b11110000, 6), (0b110000, 0b11))
