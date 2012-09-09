# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

import time
import duxlot

# 1st

@duxlot.event("1st", concurrent=True)
def startup(irc, input):
    irc.send("NICK", irc.options["nick"])
    irc.send("USER", "duxlot", "8", "*", "duxlot/irc.py")

    if "password" in irc.options["__options__"]:
        irc.send("PASS", irc.options["password"])

    if "nickserv" in irc.options["__options__"]:
        irc.msg("NickServ", "IDENTIFY %s" % irc.options["nickserv"])
        time.sleep(2)

    for channel in irc.options["channels"]:
        if (" " in channel) or ("," in channel):
            print("Not a valid channel name: %s" % channel)
        else:
            irc.send("JOIN", channel)
        time.sleep(0.25)
    time.sleep(0.5)

    irc.send("WHO", irc.options["nick"])

# 352 (WHO Result)

@duxlot.event("352")
def who(irc, input):
    if input.message["parameters"][0] == irc.options["nick"]:
        nick = input.message["parameters"][0]
        user = input.message["parameters"][2]
        host = input.message["parameters"][3]
        irc.data["address"] = nick + "!" + user + "@" + host

# 433 (Nickname in Use)

@duxlot.event("433")
def nick_error(irc, input):
    if not ("address" in irc.data):
        # haven't connected yet, panic!
        # @@ if a QUIT isn't sent, it actually hangs
        irc.send("QUIT", "Quit")
        irc.task(("quit",))

# NICK

@duxlot.event("NICK")
def set_nick(irc, input):
    if input.nick == irc.options["nick"]:
        irc.options["nick"] =     input.message["parameters"][0]

# PING

@duxlot.event("PING")
def pong(irc, input):
    irc.send("PONG", irc.options["nick"])

# PONG

@duxlot.event("PONG")
def received_pong(irc, input):
    irc.data["ponged"] = time.time()

# @duxlot.startup
# def check_channels():
#     if... ah, fuuuu
