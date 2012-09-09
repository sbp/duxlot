# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

# python3 setup.py sdist --formats=bztar

import sys
import distutils.core

import api

if sys.version_info < (3, 2):
    print("Error: Requires python 3.2 or later", file=sys.stderr)
    sys.exit(1)

README = r"""
Duxlot_ is a new IRC bot created in 2012 by `Sean B. Palmer`_, the maker of the
popular Phenny_. Features include a fast multiprocess based architecture,
modularity, and ease of use. Duxlot has no dependencies except Python3, and will
even work without having to be installed as as package.

.. _Duxlot: http://inamidst.com/duxlot/
.. _Sean B. Palmer: http://inamidst.com/sbp/
.. _Phenny: http://inamidst.com/phenny/

    **WARNING:** This is an early, pre-release alpha version of Duxlot. The API
    and features may change wildly, and the bot may not be stable.
"""

# http://stackoverflow.com/questions/4384796
# http://packages.python.org/distribute/

distutils.core.setup(
    name="duxlot",
    version=api.clock.version_number(),
    author="Sean B. Palmer",
    url="http://inamidst.com/duxlot/",
    description="Duxlot IRC Bot",
    long_description=README,
    packages=["duxlot"],
    package_dir={"duxlot": ""},
    package_data={"duxlot": ["README.rst", "data/*.*", "standard/*.*"]},
    scripts=["duxlot"],
    platforms=[
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX"
    ],
    license="License :: OSI Approved :: Apache Software License"
)
