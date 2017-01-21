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
AAAA = 28
SRV = 33
ANY = 255

def _is_type(name):
    return not name.startswith('_') and name.upper() == name

_NAME_MAPPING = dict((name, code) for name, code in globals().items() if _is_type(name))
_CODE_MAPPING = dict((code, name) for name, code in globals().items() if _is_type(name))

def get_name(code, default=None):
    '''
    Get type name from code
    '''
    name = _CODE_MAPPING.get(code, default)
    if name is None:
        name = str(code)
    return name

def get_code(name, default=None):
    '''
    Get code from type name
    '''
    return _NAME_MAPPING.get(name, default)
