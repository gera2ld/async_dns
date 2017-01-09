import sys, winreg

def _nt_read_key(lm, key):
    regkey = winreg.OpenKey(lm, key)
    try:
        value, rtype = winreg.QueryValueEx(regkey, 'NameServer')
        if not value:
            value, rtype = winreg.QueryValueEx(regkey, 'DhcpNameServer')
    except:
        value = None
    regkey.Close()
    if value:
        sep = ',' if ',' in value else ' '
        return value.split(sep)

def _nt_is_enabled(lm, guid):
    connection_key = winreg.OpenKey(lm, r'SYSTEM\CurrentControlSet\Control\Network\{4D36E972-E325-11CE-BFC1-08002BE10318}\%s\Connection' % guid)
    (pnp_id, ttype) = winreg.QueryValueEx(connection_key, 'PnpInstanceID')
    device_key = winreg.OpenKey(lm, r'SYSTEM\CurrentControlSet\Enum\%s' % pnp_id)
    try:
        flags, ttype = winreg.QueryValueEx(device_key, 'ConfigFlags')
        return not (flags & 0x1)
    finally:
        device_key.Close()
    connection_key.Close()
    return False

def get_servers():
    nameservers = []
    lm = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
    servers = _nt_read_key(lm, r'SYSTEM\CurrentControlSet\Services\Tcpip\Parameters')
    if servers is not None: nameservers.extend(servers)
    interfaces = winreg.OpenKey(lm, r'SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces')
    i = 0
    while True:
        try:
            guid = winreg.EnumKey(interfaces, i)
            i += 1
            if not _nt_is_enabled(lm, guid): continue
            servers = _nt_read_key(interfaces, guid)
            if servers is not None: nameservers.extend(servers)
        except EnvironmentError:
            break
    interfaces.Close()
    lm.Close()
    return nameservers
