'''
Constants of DNS types.
'''

NONE = 0
A = 1
NS = 2
CNAME = 5
SOA = 6
PTR = 12
MX = 15
TXT = 16
AAAA = 28
SRV = 33
NAPTR = 35
ANY = 255

def _is_type(name):
    return not name.startswith('_') and name.upper() == name

_name_mapping = {}
_code_mapping = {}

for name, code in list(globals().items()):
    if _is_type(name):
        _name_mapping[name] = code
        _name_mapping[name.lower()] = code
        _code_mapping[code] = name

def get_name(code, default=None):
    '''
    Get type name from code
    '''
    name = _code_mapping.get(code, default)
    if name is None:
        name = str(code)
    return name

def get_code(name, default=None):
    '''
    Get code from type name
    '''
    return _name_mapping.get(name, default)
