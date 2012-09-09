# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

class Storage(object):
    __slots__ = ("__attributes",)

    def __init__(self, attributes=None):
        if isinstance(attributes, dict):
            attributes = attributes.copy()
        elif attributes is None:
            attributes = {}
        else:
            name = type(attributes).__name__
            raise TypeError("expected 'dict', got '%s'" % name)
        object.__setattr__(self, "_Storage__attributes", attributes)

    def __str__(self):
        # So how come .__class__ works here?
        return "%s(**%s)" % (self.__class__.__name__, self())

    def __getattr__(self, name):
        return object.__getattribute__(self, "_Storage__attributes")[name]

    def __setattr__(self, name, value):
        object.__getattribute__(self, "_Storage__attributes")[name] = value

    def __contains__(self, name):
        return name in object.__getattribute__(self, "_Storage__attributes")

    def __call__(self, name=None, default=None):
        attributes = object.__getattribute__(self, "_Storage__attributes")
        if name is None:
            return attributes.copy()
        if name in attributes:
            return attributes[name]
        return default

class FrozenStorage(Storage):
    def __setattr__(self, name, value):
        raise AttributeError("'FrozenStorage' attributes cannot be set")
