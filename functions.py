# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

commands = {}

def register(name, function):
    "Register a function as an IRC command"
    if name in commands:
        print("Warning: Duplicate command: %s"  % name)
    commands[name] = function

def command(function):
    "Decorate a function as an IRC command"
    def canonical(name):
        return name.strip("_").replace("_", "-")

    name = canonical(function.__name__)
    register(name, function)
    return function

def named(*names):
    "Decorate a function as an IRC command, with custom names"
    def decorate(function):
        for name in names:
            register(name, function)
        return function
    return decorate

events = {"high": {}, "medium": {}, "low": {}}

def event(name, concurrent=False):
    "Decorate a function to match IRC events"
    def decorate(function):
        function.concurrent = concurrent
        events["high"].setdefault(name, [])
        events["high"][name].append(function)
        return function
    return decorate

# decorators = (command, named, event)

startups = []

def startup(function):
    "Decorate a function to run on startup"
    startups.append(function)
    return function

builders = []

def builder(function):
    "Decorate a function to augment an enviroment"
    builders.append(function)
    return function

def clear():
    "Clear registered IRC commands and events"
    commands.clear()
    events["high"].clear()
    events["medium"].clear()
    events["low"].clear()
    del startups[:]
    del builders[:]
