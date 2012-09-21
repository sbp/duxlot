#!/bin/bash

# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

USER=dux

echo '$' HOME=/tmp/dux
HOME=/tmp/dux
echo

DUX=$(python3 -c 'import os; print(os.path.expanduser("~"))')

if [ $DUX != /tmp/dux ]
then echo Error: '$HOME' is not /tmp/dux
    exit 1
fi

if [ ! -f duxlot ]
then echo Error: duxlot script not found
    exit 1
fi


function duxlot() {
    echo '$' duxlot $@
    ./duxlot $@
    echo
}

function record() {
    echo '$' $@
    $@
    echo
}

#     "ALIASES_NON_REGULAR": ##########
#     "ALIASES_NOT_CONFIG": ##########
#     "ALIASES_NOT_JSON": ##########
#     "ALIASES_NOT_UTF8": ##########
#     "ALIASES_UNREADABLE": ##########
#     "ALIASES_UNWRITEABLE": ##########
#     "OPTION_DISALLOWED": ##########
#     "OPTION_UNKNOWN": ##########
#     "VALUE_DISALLOWED": ##########

#     "DIRECTORY_NON_DIRECTORY": ##########
#     "DIRECTORY_UNMAKEABLE": ##########

#     "CONFIG_UNWRITEABLE": ##########
#     "CONFIG_NON_REGULAR": ##########
#     "CONFIG_NOT_JSON": ##########
#     "CONFIG_UNREADABLE": ##########

#     "BASE_DIRECTORY_UNWRITEABLE": ##########
#     "BASE_UNUSABLE": ##########


####################################

record : Testing DIRECTORY_UNMAKEABLE

record rm -rf /tmp/dux
record touch /tmp/dux

duxlot create

record rm /tmp/dux


####################################

record : Testing DIRECTORY_NON_DIRECTORY

record rm -rf /tmp/dux

record mkdir /tmp/dux

record touch /tmp/dux/.duxlot

duxlot create


####################################

record : Testing CONFIG_UNWRITEABLE

record rm -rf /tmp/dux

record mkdir -p /tmp/dux/.duxlot

record chmod 000 /tmp/dux/.duxlot

duxlot create

record chmod 755 /tmp/dux/.duxlot


####################################

record : Testing CONFIG_NON_REGULAR

record rm -rf /tmp/dux

record mkdir -p /tmp/dux/.duxlot/duxlot.json

duxlot create


####################################

record : Testing CONFIG_NOT_JSON

record rm -rf /tmp/dux

mkdir -p /tmp/dux

echo garbage > /tmp/dux/garbage.json

duxlot start /tmp/dux/garbage.json


####################################

record : Testing CONFIG_UNREADABLE

record rm -rf /tmp/dux

record mkdir /tmp/dux

record touch /tmp/dux/unreadable.json

record chmod 000 /tmp/dux/unreadable.json

duxlot start /tmp/dux/unreadable.json

record chmod 644 /tmp/dux/unreadable.json


####################################

record : Testing BASE_DIRECTORY_UNWRITEABLE

record rm -rf /tmp/dux

record mkdir -p /tmp/dux/conf

record touch /tmp/dux/conf/config.json

record chmod 000 /tmp/dux/conf

duxlot start /tmp/dux/conf/config.json

record chmod 755 /tmp/dux/conf


####################################

record : Testing BASE_UNUSABLE

record rm -rf /tmp/dux

record mkdir /tmp/dux

record touch /tmp/dux/.json

duxlot start /tmp/dux/.json


####################################

record : Testing double create

record rm -rf /tmp/dux

duxlot create

duxlot create


####################################

record : Testing script.py options

record rm -rf /tmp/dux

mkdir /tmp/dux

duxlot

duxlot --help

duxlot --actions

duxlot --version | \
    sed -E 's/[0-9]+\.[0-9]+\.[0-9]+-[0-9]+/VERSION/'

duxlot create

duxlot -f start | head -n 14 | \
    sed -E "s!$PWD!\$PWD!; s/:[a-z]+/:irc/; s/PID [0-9]+/PID <pid>/"
echo


####################################

record rm -rf /tmp/dux
