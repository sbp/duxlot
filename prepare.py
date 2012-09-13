#!/usr/bin/env python3

# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

import re
import os

with open(os.path.expanduser("~/.duxlot-src"), "r", encoding="ascii") as f:
    DUXLOT_SRC = f.read()
DUXLOT_SRC = DUXLOT_SRC.rstrip()

os.chdir(DUXLOT_SRC)

with open("data/version", "r", encoding="ascii") as f:
	version = f.read()

version = version.rstrip()

with open("README.rst", "r", encoding="utf-8") as f:
	readme = f.read()

readme = re.sub(r"\d+\.\d+\.\d+-\d+", version, readme)

with open("README.rst", "w", encoding="utf-8") as f:
	f.write(readme)
