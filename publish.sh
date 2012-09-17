#!/bin/bash

# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

cd $(cat ~/.duxlot-src)
echo In $PWD

# @@ check diff-not-done
# @@ make diff

# @@ check that python3 setup.py --help works, first!

echo Updating version number
python3 -c 'import api; print(api.version_number())' > data/version
DUXLOT_VERSION=$(cat data/version)

echo Running python updates
python3 prepare.py

echo Cleaning up files
rm -rf ./dist/
rm -rf ./__pycache__/
find . -name '*.pyc' -exec rm {} \;
find . -name '*.pyo' -exec rm {} \;
find . -name '.DS_Store' -exec rm {} \;

echo Creating distribution, and uploading to the CheeseShop
python3 setup.py sdist --formats=bztar upload

echo Moving distribution to archive
mv dist/*.tar.bz2 ~/.duxlot/

echo Cleaning up files
rm -rf ./dist/
rm -rf ./__pycache__/
rm -rf ./duxlot-*/
find . -name '*.pyc' -exec rm {} \;
find . -name '*.pyo' -exec rm {} \;
find . -name '.DS_Store' -exec rm {} \;

echo Upload to Github
git add -A
git commit
git push -u origin master

git tag -a $DUXLOT_VERSION -m "Version $DUXLOT_VERSION"
git push --tags
