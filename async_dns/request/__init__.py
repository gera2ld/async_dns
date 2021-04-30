from .util import ConnectionPool

def clean():
    ConnectionPool.destroy_all()