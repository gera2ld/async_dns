'''
Utility methods for parsing and packing DNS record data.
'''

import struct
import os
import io

def load_name(data, offset, lower=True):
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
    data = b'.'.join(parts).decode()
    if lower:
        data = data.lower()
    return cursor, data

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

def pack_name(name, names, offset=0):
    parts = name.split('.')
    buf = io.BytesIO()
    while parts:
        subname = '.'.join(parts)
        u = names.get(subname)
        if u:
            buf.write(struct.pack('!H', 0xc000 + u))
            break
        else:
            names[subname] = buf.tell() + offset
        buf.write(pack_string(parts.pop(0)))
    else:
        buf.write(b'\0')
    return buf.getvalue()

if os.name == 'nt':
    from .nt import get_servers
    host_file = os.path.expandvars(r'%windir%\System32\drivers\etc\hosts')
elif os.name == 'posix':
    from .posix import get_servers
    host_file = '/etc/hosts'
