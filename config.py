# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

import json
import os

# Save PEP 3122!
if "." in __name__:
    from . import storage
else:
    import storage

# @@ default.py

# def call(function):
#     function()
#     del globals()[function.__name__]

def aliases_create():
    import sys
    if not directory.exists():
        directory.create()

    aliases.write({})

    print("Created duxlot configuration aliases file:", file=sys.stderr)
    print("", file=sys.stderr)
    print("   " + aliases.path, file=sys.stderr)
    print("", file=sys.stderr)

def aliases_exists(alias=None):
    if alias is not None:
        data = aliases.read()
        return alias in data

    if os.path.isfile(aliases.path):
        return True

    if os.path.exists(aliases.path):
        fail(error.ALIASES_NON_REGULAR)

    return False

def aliases_get(alias):
    data = aliases.read()
    return data.get(alias)

def aliases_put(alias, value):
    data = aliases.read()
    data[alias] = value
    aliases.write(data)
    return True

def aliases_read():
    # @@
    try: f = open(aliases.path, encoding="utf-8")
    except (OSError, IOError):
        fail(error.ALIASES_UNREADABLE)

    with f:
        try: data = json.load(f)
        except ValueError:
            fail(error.ALIASES_NOT_JSON)
        except UnicodeDecodeError:
            fail(error.ALIASES_NOT_UTF8)

    return data

def aliases_remove(alias):
    data = aliases_read()
    del data[alias]
    aliases_write(data)

def aliases_write(data):
    # @@
    try: f = open(aliases.path, "w", encoding="utf-8")
    except (OSError, IOError):
        fail(error.ALIASES_UNWRITEABLE)

    with f:
        try: json.dump(data, f)
        except (OSError, IOError):
            fail(error.ALIASES_UNWRITEABLE)

def path(name):
    name = os.path.expanduser(name)
    return os.path.abspath(name)

aliases = storage.FrozenStorage({
    "create": aliases_create,
    "exists": aliases_exists,
    "get": aliases_get,
    "path": path("~/.duxlot/aliases.json"),
    "put": aliases_put,
    "read": aliases_read,
    "remove": aliases_remove,
    "write": aliases_write
})

def base(path):
    original = path[:]

    if path.endswith(".json"):
        # Remove ".json" extension
        path = path[:-5]

    if not os.path.basename(path):
        fail(error.BASE_UNUSABLE % (path, original))

    return path

def create():
    "Create a default minimal config"
    import sys
    if not directory.exists():
        directory.create()

    data = minimal()
    write(default, data, pretty=True)

    print("Created duxlot default configuration file:", file=sys.stderr)
    print("", file=sys.stderr)
    print("   " + default, file=sys.stderr)
    print("", file=sys.stderr)

def directory_create():
    # if directory.exists():
    #     raise Exception("Directory already exists")
    import sys

    try: os.makedirs(directory.path)
    except (OSError, IOError) as err:
        msg = "%s: %s" % (err.__class__.__name__, err)
        args = (directory.path, msg)
        fail(error.DIRECTORY_UNMAKEABLE % args)

    print("Created default duxlot configuration directory:", file=sys.stderr)
    print("", file=sys.stderr)
    print("   " + directory.path, file=sys.stderr)
    print("", file=sys.stderr)

    return True

def directory_exists():
    if os.path.isdir(directory.path):
        return True

    if os.path.exists(directory.path):
        fail(error.DIRECTORY_NON_DIRECTORY)

    return False

directory = storage.FrozenStorage({
    "create": directory_create,
    "exists": directory_exists,
    "path": os.environ.get("DUXLOT_DIRECTORY", path("~/.duxlot"))
})

default = os.path.join(directory.path, "duxlot.json")

def reduceuser(path):
    home = os.path.expanduser("~/")
    if path.startswith(home):
        path = "~/" + path[len(home):]
    return path

error = storage.FrozenStorage({
    "ALIASES_NON_REGULAR": ##########
"""
The following path exists, but is not a regular file as it ought to be:

    %s

This is a very strange error, so you're on your own debugging this one. Check
to make sure you didn't accidentally create a directory there. Otherwise,
please file a bug.

(Error Name: ALIASES_NON_REGULAR)
""" % reduceuser(aliases.path),

    "ALIASES_NOT_CONFIG": ##########
"""
You are trying to use your aliases file as a config file. The aliases file for
duxlot is a JSON file, but it's not where configuration options for a duxlot
instance are stored.

This was most likely caused by a typo or through misunderstanding the duxlot
script options. If you require further help, please read the duxlot
documentation in more detail, or contact the maintainer for further information.

(Error Name: ALIASES_NOT_CONFIG)
""",

    "ALIASES_NOT_JSON": ##########
"""
Your aliases file exists but is not valid JSON:

    %s

This is probably caused by one of two reasons:

1. The file has been created as normal by duxlot, but at some point has been
edited manually and incorrectly. In this case, you may want to use a JSON
validator to see what has gone wrong, or even remove the file if it does not
contain valuable aliases and start again. JSON should be fairly easy to repair.

2. A random file has been created there for no apparent reason. This could be
due to a script malfunction or something of this nature. Check to see what the
contents of the file are, and if the file isn't important, move it to another
location.

(Error Name: ALIASES_NOT_JSON)
""" % reduceuser(aliases.path),

    "ALIASES_NOT_UTF8": ##########
"""
Your aliases.json file is not correctly encoded as utf-8:

    %s

This error may be difficult to fix. It was probably caused by one of the two
following reasons:

1. You manually edited the file and didn't save it with the correct encoding.

2. A tool at some point, possibly the term you used as an interface to duxlot,
didn't send valid utf-8 and for some reason it got through to the aliases.json
file.

You can either try to fix the encoding, which might incur the difficult task of
sweeping up mojibake, or you might want to take the easy option and just move
or even delete the file.

Learn more about utf-8 and mojibake here:

    https://en.wikipedia.org/wiki/UTF-8
    https://en.wikipedia.org/wiki/Mojibake

(Error Name: ALIASES_NOT_UTF8)
""" % reduceuser(aliases.path),

    "ALIASES_UNREADABLE": ##########
"""
Your aliases file cannot be read:

    %s

There is a file there, but duxlot is unable to access it. There is probably a
permissions error with either the file itself, or one of its parent
directories. Check to make sure that the user duxlot is running as has access
to that file.

(Error Name: ALIASES_UNREADABLE)
""" % reduceuser(aliases.path),

    "ALIASES_UNWRITEABLE": ##########
"""
Your aliases file cannot be written to:

    %s

There is a file there, but duxlot is unable to access it. There is probably a
permissions error with either the file itself, or one of its parent
directories. Check to make sure that the user duxlot is running as has write
access to that file.

(Error Name: ALIASES_UNWRITEABLE)
""" % reduceuser(aliases.path),

    "BASE_DIRECTORY_UNWRITEABLE": ##########
"""
Error: BASE_DIRECTORY_UNWRITEABLE

The directory that your duxlot configuration file is in cannot be written to:

    %s

There is a directory there, but duxlot is unable to access it. There is
probably a permissions error with either the directory itself, or one of its
parent directories. Check to make sure that the user duxlot is running as has
write access to that directory.
""", # args: 1

    "BASE_UNUSABLE": ##########
"""
Error: BASE_UNUSABLE

The following configuration base is not usable:

    %s

This usually happens when your configuration file is called just ".json"
instead of having a name before the extension, such as "config.json". The
configuration file duxlot tried to use is:

    %s

Duxlot needs a base to work with for other files. You can easily solve this by
renaming your configuration file.
""", # args: 2

    "CONFIG_NON_REGULAR": ##########
"""
Error: CONFIG_NON_REGULAR

The following path exists, but is not a regular file as it ought to be:

    %s

This problem is probably caused by trying to pass a path to what was thought to
be a JSON file but is in fact a directory.
""", # args: 1

    "CONFIG_NOT_JSON": ##########
"""
Error: CONFIG_NOT_JSON

Your duxlot configuration file exists but is not valid JSON:

    %s

The error message that the JSON parser gave is:

    %s

Which may or may not be helpful, since the duxlot maintainer does not have any
control over the Python JSON implementation. If you need help writing a valid
JSON file, try reading through the following resources:

    http://en.wikipedia.org/wiki/JSON
    http://guide.couchdb.org/draft/json.html

You may also ask the duxlot maintainer for help.
""", # args: 2

    "CONFIG_UNREADABLE": ##########
"""
Error: CONFIG_UNREADABLE

Your duxlot configuration file exists but can't be read:

    %s

There is probably a permissions error with either the file itself, or one of
its parent directories. Check to make sure that the user duxlot is running as
has access to that file.
""", # args: 1

    "CONFIG_UNWRITEABLE": ##########
"""
Error: CONFIG_UNWRITEABLE

Your duxlot configuration file exists but can't be written to:

    %s

There is probably a permissions error with either the file itself, or one of
its parent directories. Check to make sure that the user duxlot is running as
has write access to that file.
""", # args: 1

    "DIRECTORY_NON_DIRECTORY": ##########
"""
Error: DIRECTORY_NON_DIRECTORY

Your duxlot configuration directory path exists, but is not a directory:

    %s

This is probably because you have written a regular file called .duxlot in your
home directory, whereas duxlot wants that to be a directory, in order to put
the default configuration file and aliases file in it.

If you intended .duxlot to be a JSON configuration file, you can still use it
as such, but it will be incompatible with using default configuration files,
and configuration path aliases in duxlot.
""" % directory.path,

    "DIRECTORY_UNMAKEABLE": ##########
"""
Error: DIRECTORY_UNMAKEABLE

Tried to create a duxlot configuration directory here:

    %s

But the operation was not allowed. Python gave this error:

    %s

Duxlot tried to create this directory recursively, which means that it tried to
create any parent directories too. Check to make sure that duxlot can write
here. Does a regular file exist in the way? Are permissions correctly set on
the parent directory? Is the user set correctly?

If this directory cannot be created, duxlot cannot create default configuration
and configuration alias files, but can still be run without them.

To use a different default directory configuration, you can set the value of
the $DUXLOT_DIRECTORY environment variable to another directory. Duxlot will
attempt to create this, too, if it does not yet exist.
""", # args: 2

    "OPTION_DISALLOWED": ##########
"""
Your configuration file contains a disallowed option:

    %s

These options are reserved by duxlot for internal use. Please remove this
option from your configuration file, and try again.

(Error Name: OPTION_DISALLOWED)
""" # args: 1
})

def exists(path):
    if os.path.isfile(path):
        return True

    if os.path.exists(path):
        fail(error.CONFIG_NON_REGULAR % path)

    return False

def fail(explanation):
    import sys

    sys.stderr.write(explanation.lstrip())
    sys.exit(1)

def info(name):
    if name is None:
        if not exists(default):
            create()
        name = default

    config_base = base(name)
    config_base_directory = os.path.dirname(config_base)
    if not writeable(config_base_directory):
        fail(error.BASE_DIRECTORY_UNWRITEABLE % config_base_directory)

    config_data = read(name)

    # @@ Could be a FrozenStorage object
    return name, config_base, config_data

def random_nick():
    import random
    return "duxlot%03i" % random.randrange(1000)

def minimal():
    return {
        "address": "irc.freenode.net:6667",
        "nick": random_nick(),
        "start-channels": ["#duxlot-test"]
    }

def pretty(data):
    return json.dumps(data, sort_keys=True, indent=4)

def read(path):
    if path.startswith("~") or (not path.startswith("/")):
        raise ValueError("Path not canonical: %s" % path)

    if path == aliases.path:
        fail(error.ALIASES_NOT_CONFIG)

    try: f = open(path, encoding="utf-8")
    except (OSError, IOError):
        fail(error.CONFIG_UNREADABLE % path)

    with f:
        try: data = json.load(f)
        except ValueError as err:
            fail(error.CONFIG_NOT_JSON % (path, err))
        except UnicodeDecodeError:
            fail(error.CONFIG_NOT_UTF8)

    if "__options__" in data:
        fail(error.OPTION_DISALLOWED % "__options__")

    data["__options__"] = set(data.keys())

    return data

def write(path, data, pretty=False):
    if "__options__" in data:
        for name in list(data.keys()):
            if name == "__options__":
                continue

            if name not in data["__options__"]:
                del data[name]
        del data["__options__"]

    # @@ functionise this and put it in a try/except
    try: f = open(path, "w", encoding="utf-8")
    except (OSError, IOError):
        fail(error.CONFIG_UNWRITEABLE % path)

    with f:
        if pretty:
            text = globals()["pretty"](data)
            try: f.write(text)
            except (OSError, IOError):
                fail(error.CONFIG_UNWRITEABLE % path)
        else:
            try: json.dump(data, f)
            except (OSError, IOError):
                fail(error.CONFIG_UNWRITEABLE % path)

    return True

def writeable(base):
    # @@ Not a perfect check
    return os.access(base, os.W_OK)
