# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

import multiprocessing
import os
import readline
import sys

import duxlot

# Turn off buffering, like python3 -u
# http://stackoverflow.com/questions/107705

class Unbuffered:
    def __init__(self, stream):
        self.stream = stream # @@ __stream

    def write(self, data):
        self.stream.write(data)
        self.stream.flush()

    def __getattr__(self, attr):
        return getattr(self.stream, attr)

sys.stdout = Unbuffered(sys.stdout)
sys.stderr = Unbuffered(sys.stderr)

# @@ this is used in script.py too
# move to duxlot.unbuffered()?

# This is only a class to work around Python Issue 15914:
# http://bugs.python.org/issue15914
# (Note: not using multiprocessing here currently, anyway)

class Console(object):
    def __init__(self):
        # @@ Use the base resolution code in script.py
        self.base = os.path.expanduser("~/.duxlot-console")
        self.database = duxlot.database(self.base)

    def create_console_env(self, text):
        env = duxlot.Storage()
    
        if text.startswith("."):
            text = text[1:]
            if " " in text:
                env.command, env.arg = text.split(" ", 1)
            else:
                env.command, env.arg = text, ""
    
        env.database = self.database
        env.sender = "__console__"
        env.nick = os.environ.get("USER")
        env.limit = 512
    
        def say(text):
            print(text)
        env.say = say
        env.reply = say
    
        return env
    
    def start(self):
        print("Loading duxlot configuration...")

        sys.path[:1] = [os.path.join(duxlot.path, "standard"), duxlot.path]
    
        import general    
    
        named = duxlot.commands.copy()
        events = duxlot.events.copy()
        for startup in duxlot.startups:
            startup(self) # @@ safe in irc.py
    
        for event in events["high"]["1st"]:
            event(self.create_console_env(""))
    
        print("Welcome to duxlot %s, console edition" % duxlot.version)
        while True:
            try: text = input("$ ")
            except (EOFError, KeyboardInterrupt):
                print("")
                print("Quitting...")
                break
    
            env = self.create_console_env(text)
            if "command" in env:
                if env.command in named:
                    try: named[env.command](env)
                    except Exception as err:
                        print("%s: %s" % (err.__class__.__name__, err))
                else:
                    print("Unknown command: %s" % env.command)
            else:
                print("Commands start with \".\"")

def main():
    console = Console()
    console.start()

if __name__ == "__main__":
    # Run this using duxlot --console, though
    main()
