'''
Script to resolve hostnames.
'''
import argparse
import asyncio
from async_dns.core import *
from . import ProxyResolver

def _parse_args():
    parser = argparse.ArgumentParser(
        prog='python3 -m async_dns.resolver',
        description='Async DNS resolver')
    parser.add_argument('hostnames', nargs='+', help='the hostnames to query')
    parser.add_argument('-n', '--nameservers', nargs='+', help='name servers')
    parser.add_argument(
        '-t', '--types', nargs='+', default=['any'],
        help='query types, default as `any`')
    return parser.parse_args()

async def resolve_hostname(resolver, hostname, qtype):
    '''Resolve a hostname with the given resolver.'''
    addr = Address.parse(hostname, allow_domain=True)
    if addr.ip_type is None:
        return await resolver.query(hostname, qtype)
    else:
        res = DNSMessage()
        res.qd.append(Record(REQUEST, name=hostname, qtype=addr.ip_type))
        res.an.append(Record(qtype=addr.ip_type, data=hostname))
        return res

async def resolve_hostnames(args):
    '''Resolve hostnames passed from process arguments.'''
    resolver = ProxyResolver()
    if args.nameservers:
        resolver.set_proxies(args.nameservers)
    results = []
    for hostname in args.hostnames:
        for qtype_name in args.types:
            qtype = types.get_code(qtype_name.upper())
            if qtype is None:
                logger.warn('Unknown type: %s', qtype_name)
                continue
            results.append(asyncio.ensure_future(resolve_hostname(resolver, hostname, qtype)))
    done, _ = await asyncio.wait(results, timeout=3)
    for fut in done:
        res = fut.result()
        hostname = res.qd[0].name
        for item in res.an:
            print('%s [%s] %s' % (
                hostname,
                types.get_name(item.qtype),
                item.data,
            ))

# asyncio.run is added in 3.7
loop = asyncio.get_event_loop()
loop.run_until_complete(resolve_hostnames(_parse_args()))
