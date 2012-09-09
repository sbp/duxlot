# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

path = None

if "__file__" in vars():
    if __file__:
        import os.path

        path = os.path.abspath(__file__)
        path = os.path.dirname(path)

        del os

if "__path__" in vars():
    if __path__:
        for directory in __path__:
            if path is None:
                path = directory
            elif path != directory:
                raise Exception("Can't create duxlot.path")

        del directory

# Save PEP 3122!
if "." in __name__:
    from . import config
    from . import script

    from .functions import *
    from .storage import *
else:
    import config
    import script

    from functions import *
    from storage import *

def client(*args, **kargs):
    # Save PEP 3122!
    if "." in __name__:
        from .irc import Client
    else:
        from irc import Client
    Client(*args, **kargs)
