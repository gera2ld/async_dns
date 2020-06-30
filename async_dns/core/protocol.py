class InternetProtocol:
    protocols = {}

    def __init__(self, name):
        self.protocol = name
        self.protocols[name] = self

    def __str__(self):
        return self.protocol

    def __repr__(self):
        return f'<InternetProtocol {self.protocol}>'

    @classmethod
    def get(cls, name):
        if isinstance(name, cls):
            return name
        if isinstance(name, str):
            name = name.lower()
        return cls.protocols.get(name, UDP)

UDP = InternetProtocol('udp')
TCP = InternetProtocol('tcp')
