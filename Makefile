# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

SHELL = /bin/sh
makefile = $(lastword $(MAKEFILE_LIST))

.PHONY: all help targets
all help targets:
	@## Show Makefile targets and their functions
	@sed -n '/^.@*## /{s/@*## //;x;s/:.*//;G;p;};h' $(makefile)

.PHONY: dist
dist:
	@## Make a .bz2 tarball using setup.py
	python3 setup.py sdist --formats=bztar

.PHONY: edit
edit:
	@## Edit all files in the duxlot source
	edit *.py duxlot standard/*.* test/*.*

.PHONY: publish
publish:
	@## Publish a version to pypi and github
	bash publish.sh

.PHONY: pypitest
pypitest:
	@## Push a test distribution to testpypi
	python3 setup.py sdist --formats=bztar upload -r test

.PHONY: update
update:
	@## Update from source directory
	# @@
