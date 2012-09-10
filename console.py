#!/usr/bin/env python3

# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

import multiprocessing
import os
import readline
import sys

import duxlot

if "." in __name__:
    from . import irc
else:
    import irc

base = os.path.expanduser("~/.duxlot-console")
manager = multiprocessing.Manager()
database = irc.create_database_interface(base, manager)

def create_console_env(text):
    env = duxlot.Storage()

    if text.startswith("."):
        text = text[1:]
        if " " in text:
            env.command, env.arg = text.split(" ", 1)
        else:
            env.command, env.arg = text, ""

    env.database = database
    env.sender = "__console__"
    env.nick = os.environ.get("USER")
    env.limit = 512

    def say(text):
        print(text)
    env.say = say
    env.reply = say

    return env

def main():
    sys.path[:1] = [os.path.join(duxlot.path, "standard"), duxlot.path]

    import general    

    named = duxlot.commands.copy()
    events = duxlot.events.copy()
    for startup in duxlot.startups:
        startup()

    for event in events["high"]["1st"]:
        event(create_console_env(""))

    while True:
        try: text = input("$ ")
        except EOFError:
            print("")
            print("Quitting...")
            break

        env = create_console_env(text)
        if "command" in env:
            if env.command in named:
                try: named[env.command](env)
                except Exception as err:
                    print("%s: %s" % (err.__class__.__name__, err))
            else:
                print("Unknown command: %s" % env.command)
        else:
            print("Commands start with \".\"")

if __name__ == "__main__":
    main()
