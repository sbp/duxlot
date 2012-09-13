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

def populate():
    global filesystem
    global output

    import contextlib
    import multiprocessing

    filesystem = Storage()

    filesystem.lock = multiprocessing.RLock()

    @contextlib.contextmanager
    def filesystem_open(*args, **kargs):
        with filesystem.lock:
            yield open(*args, **kargs)
    filesystem.open = filesystem_open

    output = Storage()

    output.lock = multiprocessing.RLock()

    def output_write(*args, **kargs):
        with output.lock:
            print(*args, **kargs)
    output.write = output_write

populate()

del populate

def database(base, cache=None):
    import contextlib
    import json
    import multiprocessing
    import os.path
    import pickle

    if cache is None:
        cache = Storage()

    base = os.path.expanduser(base)
    dotdb = base + ".%s.db"
    dotjson = base + ".%s.json"

    def check(name):
        if not name.isalpha():
            raise ValueError(name)

    def do_load(name):
        filename = dotdb % name
        if os.path.isfile(filename):
            with filesystem.open(filename, "rb") as f:
                return pickle.load(f)

    def do_dump(name, data):
        with filesystem.open(dotdb % name, "wb") as f:
            pickle.dump(data, f)

    # @@ init, copies to cache returns a fallback?
    # e.g. irc.safe.database.init("name", [])

    def init(name, default=None):
        data = do_load(name) or default
        setattr(cache, name, data)
        if data is default:
            do_dump(name, data)

    def load(name):
        check(name)
        with filesystem.lock:
            return do_load(name)

    def dump(name, data):
        check(name)
        with filesystem.lock:
            do_dump(name, data)

    @contextlib.contextmanager
    def context(name):
        check(name)
        with filesystem.lock:
            data = getattr(cache, name)
            yield data
            setattr(cache, name, data)
            do_dump(name, data)

    def export(name): # remove this? export base instead?
        check(name)
        with filesystem.lock:
            data = do_load(name)
            filename = dotjson % name
            with filesystem.open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f)
            return filename

    return FrozenStorage({
        "init": init,
        "load": load,
        "dump": dump,
        "context": context,
        "export": export,
        "cache": cache
    })
