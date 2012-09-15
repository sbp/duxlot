# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

import multiprocessing
import os
import readline
import sys

import duxlot

# Save PEP 3122!
if "." in __name__:
    from . import api
else:
    import api

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

# @@ a variant of this is used in script.py too
# consolidate? move to duxlot.unbuffered()?

# This is only a class to work around Python Issue 15914:
# http://bugs.python.org/issue15914
# (Note: not using multiprocessing here currently, anyway)

class Console(object):
    def __init__(self):
        self.commands = {}
        self.setup()

    def setup(self):
        print("Loading duxlot API configuration...")
        api.clock.cache_timezones_data()
        api.unicode.cache_unicode_data()

        services = api.text()
        services = services.copy()
        del services["name"]

        for name in services:
            def create(name):
                def command(text):
                    return services[name](
                        text=text,
                        maximum={
                            "bytes": 1024,
                            "lines": 3
                        }
                    )
                return command
            self.commands[name] = create(name)

    def start(self):
        print("Welcome to duxlot %s, console edition" % duxlot.version)
        while True:
            try: text = input("$ ")
            except (EOFError, KeyboardInterrupt):
                print("")
                print("Quitting...")
                break
    
            if text.startswith("."):
                text = text[1:]

            if " " in text:
                command, text = text.split(" ", 1)
            else:
                command, text = text, ""

            if command in self.commands:
                try: response = self.commands[command](text)
                except api.Error as err:
                    print("Error:", err)
                except Exception as err:
                    print("Script Error:", err)
                else:
                    for line in response.split("\n"):
                        print(line)
            else:
                print("Unknown command: %s" % command)

def main():
    console = Console()
    console.start()

if __name__ == "__main__":
    # Run this using duxlot --console, though
    main()
