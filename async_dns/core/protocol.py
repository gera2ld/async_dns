class InternetProtocol:
    protocols = {}

    def __init__(self, name):
        self.protocol = name
        self.protocols[name] = self

    @classmethod
    def get(cls, name):
        if isinstance(name, cls):
            return name
        if isinstance(name, str):
            name = name.lower()
        return cls.protocols.get(name, UDP)

UDP = InternetProtocol('udp')
TCP = InternetProtocol('tcp')
