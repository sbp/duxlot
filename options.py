# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

import json
import re

import duxlot

def canonicalise(name):
    name = name.strip("_")
    return name.replace("_", "-")

class Option(object):
    "Configuration file option and value pairs"
    default = None
    types = {type(None), str}

    def __init__(self, group, manager, public):
        local = canonicalise(self.__class__.__name__)
        self.name = group + "-" + local if group else local

        self.public = public
        self.data = manager.Namespace()
        self.data.value = None # @@ _value? __value?

        self.put(self.default, react=False)

    def check(self, value):
        if not (type(value) in self.types):
            msg = "Type disallowed: %s: %s not in %s"
            raise TypeError(msg % (self.name, value, self.types))

        try: json.dumps(value)
        except Exception as err:
            raise TypeError(str(err))

    def put(self, value, react=True):
        self.check(value)

        if value == self.data.value:
            return False

        try: data = self.parse(value)
        except Exception as err:
            raise ValueError(str(err))
        else:
            self.data.value = value
            if data:
                for a, b in data.items():
                    if a == "value":
                        continue # ?
                    setattr(self.data, a, b)
            if react is True:
                self.react()

            return True

    def regexp(self, pattern, value):
        return re.match("^%s$" % pattern, value)

    def reset(self):
        self.put(self.default)

    def parse(self, value):
        ...

    def react(self):
        ...

class Options(object):
    option = Option

    def __init__(self, filename, manager, public):
        import collections

        self.filename = filename
        self.manager = manager
        self.public = public
        self.map = manager.Namespace()
        self.map.pings = collections.OrderedDict()
        self.__options = {}
        self.completed = set()

    def __call__(self, name, attr=None):
        if attr is None:
            return self.__options[name].data.value
        else:
            return getattr(self.__options[name].data, attr)

    # This is a decorator
    def group(self, name=None):
        if name in self.completed:
            raise ValueError("the %r group is complete" % name)

        def decorate(definition):
            option = definition(name, self.manager, self.public)
            self.__options[option.name] = option
        return decorate

    # This is used after the decorators
    def complete(self, name=None):
        # @@ Check that this group name has been used?
        self.completed.add(name)

    def load(self, react=True, validate=True):
        # When loading initially, react=False!
        # Note that this method will also validate input
        import collections

        args = (self.filename, "r")
        with duxlot.filesystem.open(*args, encoding="utf-8") as f:
            mappings = json.load(f, object_pairs_hook=collections.OrderedDict)

        self.map.pings.clear()
        for key, value in mappings.items():
            if validate is False:
                if not (key in self.__options):
                    continue
            # No need to dump, because we've literally just read it
            # The react param will be False for initial load, True for reloads
            if isinstance(value, collections.OrderedDict):
                value = dict(value)
            self.put(key, value, react=react, dump=False)

    def put(self, key, value, react=True, dump=True):
        self.__options[key].put(value, react=react)

        mappings = self.map.pings
        mappings[key] = value
        self.map.pings = mappings

        if dump is True:
            return self.dump()

    def dump(self):
        def export(self):
            import shutil

            # Create strings first, in case JSONising fails half way through
            strings = ["{"]
            for key, value in self.map.pings.items():
                pair = json.dumps(key) + ": " + json.dumps(value) + ","
                strings.append("    " + pair)
            strings[-1] = strings[-1].rstrip(",")
            strings.append("}")

            # Write to .export first, in case writing fails half way through
            args = (self.filename + ".export", "w")
            with duxlot.filesystem.open(*args, encoding="utf-8") as f:
                for string in strings:
                    f.write(string + "\n")

            # @@ Might have to be non-re-entrant, because load uses
            # the same lock. Do we need that to block?
            with duxlot.filesystem.lock:
                shutil.copy2(self.filename, self.filename + ".backup")
                shutil.move(self.filename + ".export", self.filename)

        try: export(self)
        except Exception as err:
            duxlot.output.write(err)
            return False
        else:
            return True
