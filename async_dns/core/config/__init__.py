import os
from .root import *

if os.name == 'nt':
    from .nt import get_nameservers
elif os.name == 'posix':
    from .posix import get_nameservers
