# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

# python3 setup.py sdist --formats=bztar

import os.path
import sys
import distutils.core

import api

# Require 3.2.2 because of http://bugs.python.org/issue12576
if sys.version_info < (3, 2, 2):
    print("Error: Requires python 3.2.2 or later", file=sys.stderr)
    sys.exit(1)

with open(os.path.join("data", "version"), encoding="ascii") as f:
    version = f.read()
    version = version.rstrip()

README = r"""
Duxlot_ is a new IRC bot created by `Sean B. Palmer`_, the maker of the popular
Phenny_. Features include a fast multiprocess architecture, modularity, and
ease of use. Duxlot has no dependencies except Python 3, and will even work
without having to be installed as as package. `Source on Github`_.

.. _Duxlot: http://inamidst.com/duxlot/
.. _Sean B. Palmer: http://inamidst.com/sbp/
.. _Phenny: http://inamidst.com/phenny/
.. _Source on Github: https://github.com/sbp/duxlot

Install
---------

    **WARNING:** This is an pre-release alpha version of Duxlot. The API and
    features may change, and the bot may not be stable.

You may use **either** of these methods:

*   Download the `latest source`_. Unpack it and enter ``duxlot-%s/``

    **Optionally** install using::

        python3 setup.py install

*   OR: Install using pip_::

        pip install duxlot

.. _latest source: http://pypi.python.org/pypi/duxlot#downloads
.. _pip: http://pypi.python.org/pypi/pip

**Optionally** use virtualenv_ for either of these methods.

.. _virtualenv: http://www.virtualenv.org/en/latest/index.html#installation

You can now use the ``duxlot`` script. Try ``duxlot --help``.
""" % version

# http://stackoverflow.com/questions/4384796
# http://packages.python.org/distribute/

if __name__ == "__main__":
    distutils.core.setup(
        name="duxlot",
        version=version,
        author="Sean B. Palmer",
        url="http://inamidst.com/duxlot/",
        description="IRC bot and data suite, by the maker of phenny",
        long_description=README,
        packages=["duxlot"],
        package_dir={"duxlot": ""},
        package_data={"duxlot": [
            "README.rst", "data/*", "standard/*", "test/*"
        ]},
        scripts=["duxlot"],
        # @@ pypi changes ", " to "," in platforms, removing spaces
        # Could try using an nbsp, perhaps
        platforms="Linux and OS X",
        classifiers=[
            "License :: OSI Approved :: Apache Software License",
            "Operating System :: MacOS :: MacOS X",
            "Operating System :: POSIX",
            "Programming Language :: Python :: 3"
        ],
        license="Apache License 2.0"
    )
