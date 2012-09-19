# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

import time
import duxlot

# 1st

@duxlot.event("1st", concurrent=True)
def startup(env):
    env.send("NICK", env.options("nick"))
    env.send("USER", "duxlot", "8", "*", "duxlot/env.py")

    if env.options("start-password") is not None:
        env.send("PASS", env.options("start-password"))

    if env.options("start-nickserv") is not None:
        env.msg("NickServ", "IDENTIFY %s" % env.options("start-nickserv"))
        if not env.options("flood"):
            time.sleep(2)

    for channel in env.options("start-channels"):
        if (" " in channel) or ("," in channel):
            duxlot.output.write("Not a valid channel name: %s" % channel)
        else:
            env.send("JOIN", channel)
        if not env.options("flood"):
            time.sleep(0.25)
    if not env.options("flood"):
        time.sleep(0.5)

    env.send("WHO", env.options("nick"))

# 352 (WHO Result)

@duxlot.event("352")
def who(env):
    if env.message["parameters"][0] == env.options("nick"):
        nick = env.message["parameters"][0]
        user = env.message["parameters"][2]
        host = env.message["parameters"][3]
        env.data["address"] = nick + "!" + user + "@" + host

# 433 (Nickname in Use)

@duxlot.event("433")
def nick_error(env):
    if not ("address" in env.data):
        # haven't connected yet, panic!
        # @@ if a QUIT isn't sent, it actually hangs
        env.send("QUIT", "Quit")
        env.task("quit")

# NICK

@duxlot.event("NICK")
def set_nick(env):
    if env.nick == env.options("nick"):
        env.options.put("nick", env.message["parameters"][0])

# PING

@duxlot.event("PING")
def pong(env):
    env.send("PONG", env.options("nick"))

# PONG

@duxlot.event("PONG")
def received_pong(env):
    env.data["ponged"] = time.time()

@duxlot.startup
def startup(public):
    if "start" in public.options.completed:
        return

    group = public.options.group
    option = public.options.option

    @group("start")
    class channels(option):
        default = []
        types = {list}

    # @@ why doesn't default: None and types: {str} raise an issue?
    @group("start")
    class nickserv(option):
        ...

    @group("start")
    class password(option):
        ...

    public.options.complete("start")
