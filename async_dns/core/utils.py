'''
Utility methods for parsing and packing DNS record data.
'''

import struct
import io


class ParseError(Exception):
    def __init__(self, data, offset, message):
        super().__init__()
        self.data = data
        self.offset = offset
        self.message = message

    def __repr__(self):
        return f'''<ParseError
    message={self.message}
    offset={self.offset}
    data_len={len(self.data)}
    data={self.data}>'''


def load_domain_name(buffer, offset):
    '''Load a domain name from packed data'''
    parts = []
    cursor = None
    data_len = len(buffer)
    visited = set()
    while offset < data_len:
        if offset in visited:
            raise ParseError(buffer, offset, 'Pointer loop detected')
        visited.add(offset)
        length = buffer[offset]
        offset += 1
        if length == 0:
            if cursor is None:
                cursor = offset
            break
        if length >= 0xc0:
            if cursor is None:
                cursor = offset + 1
            offset = (length - 0xc0) * 256 + buffer[offset]
            continue
        parts.append(buffer[offset:offset + length])
        offset += length
    if cursor is None:
        raise ParseError(buffer, offset, 'Bad data')
    data = b'.'.join(parts).decode()
    return cursor, data


def load_string(buffer, offset):
    '''Load a character string from packed data.'''
    length = buffer[offset]
    offset += 1
    data = buffer[offset:offset + length]
    return offset + length, data


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


def pack_domain_name(name, names, offset=0):
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
