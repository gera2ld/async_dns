'''
Utility methods for parsing and packing DNS record data.
'''

import struct
import os

def load_name(data, offset):
    '''Return the full name and offset from packed data.'''
    parts = []
    cursor = None
    while True:
        length = ord(data[offset : offset + 1])
        offset += 1
        if length == 0:
            if cursor is None:
                cursor = offset
            break
        elif length >= 0xc0:
            if cursor is None:
                cursor = offset + 1
            offset = (length - 0xc0) * 256 + ord(data[offset : offset + 1])
            continue
        parts.append(data[offset : offset + length])
        offset += length
    return cursor, b'.'.join(parts).decode().lower()

def pack_string(string, btype='B'):
    '''Pack string into `{length}{data}` format.'''
    if not isinstance(string, bytes):
        string = string.encode()
    length = len(string)
    return struct.pack('%s%ds' % (btype, length), length, string)

def get_bits(num, bit_len):
    '''Get lower and higher bits breaking at bit_len from num.'''
    high = num >> bit_len
    low = num - (high << bit_len)
    return low, high

if os.name == 'nt':
    from .nt import get_servers
    host_file = os.path.expandvars(r'%windir%\System32\drivers\etc\hosts')
elif os.name == 'posix':
    from .posix import get_servers
    host_file = '/etc/hosts'
