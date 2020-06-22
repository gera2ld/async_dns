'''
Utility methods for parsing and packing DNS record data.
'''

import struct
import io

class ParseError(Exception):
    def __init__(self, data, offset):
        super().__init__()
        self.data = data
        self.offset = offset

    def __repr__(self):
        return f'''<ParseError
    offset={self.offset}
    data_len={len(self.data)}
    data={self.data}>'''

def load_message(data, offset, lower=True):
    '''Return the full name and offset from packed data.'''
    parts = []
    cursor = None
    data_len = len(data)
    while offset < data_len:
        length = data[offset]
        offset += 1
        if length == 0:
            if cursor is None:
                cursor = offset
            break
        if length >= 0xc0:
            if cursor is None:
                cursor = offset + 1
            offset = (length - 0xc0) * 256 + data[offset]
            continue
        parts.append(data[offset : offset + length])
        offset += length
    assert cursor is not None, ParseError(data, offset)
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

def pack_message(name, names, offset=0):
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
