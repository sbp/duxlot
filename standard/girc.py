# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

# @@ this can't be named irc.py

import duxlot

# Save PEP 3122!
if "." in __name__:
    from . import api
else:
    import api

command = duxlot.command

# @@ ask, not tell yourself
# IRC
@command
def ask(env):
    "Ask another user an enquiry"
    if not env.arg:
        return env.reply(ask.__doc__)

    env.verb = "ask"
    to(env)

# IRC
@command
def parsed_message(env):
    "Show parsed input message"
    env.reply(repr(env.message))

# IRC
@command
def schedule(env):
    "Schedule an event"
    # @@ database.timezones
    if not env.arg:
        return env.reply(schedule.__doc__)

    t, text = env.arg.split(" ", 1)
    t = float(t)
    env.schedule((t, env.sender, env.nick, text))
    env.reply("Scheduled")

# @@ test to make sure the right time is given!
# IRC
@command
def seen(env):
    "Find out whether somebody has been around recently"
    if not env.arg:
        return env.say(seen.__doc__)

    if env.arg == env.options["nick"]:
        return env.reply("I'm right here")

    # env.database.seen.get.verb.verb.verb
    result = env.database.cache.seen.get(env.arg)

    if not result:
        env.say("Haven't seen %s" % env.arg)
    else:
        unixtime, place = result

        offset, abbreviation = zone_from_nick(env, env.nick)
        dt = api.clock.format_datetime(
            format="%Y-%m-%d %H:%M:%S $TZ",
            offset=offset,
            tz=abbreviation,
            unixtime=unixtime
        )

        env.say("On %s at %s" % (place, dt))

# IRC
# @@ a check that commands are covered here
@command
def stats(env):
    "Display information about the most used commands"
    usage = env.database.cache.usage

    usage = sorted(((b, a) for (a, b) in usage.items()), reverse=True)
    usage = list(usage)[:10]
    usage = ["%s (%s)" % (b, a) for (a, b) in usage]
    env.reply("Top used commands: " + ", ".join(usage))

# IRC
@command
def tell(env):
    "Tell another user a message"
    # Inspired by Monty, by Paul Mutton
    # http://www.jibble.org/

    if not env.arg:
        return env.reply(tell.__doc__)

    env.verb = "tell"
    to(env)

# IRC
@command
def timezone(env):
    "Set the user's timezone to an IANA Time Zone Database value"
    tz = env.database.cache.timezones.get(env.nick, None)

    if not env.arg:        
        if tz:
            return env.reply("Your timezone is currently set to %s" % tz)
        else:
            return env.reply("You do not currently have a timezone set")

    if env.arg in {"None", "-", "delete", "remove", "unset"}:
        if tz is None:
            return env.reply("You do not current have a timezone set")
        with env.database.context("timezones") as timezones:
            del timezones[env.nick]
        return env.reply("Your timezone has been un-set")

    if env.arg in {"geo", "guess"}:
        zonename = api.geo.timezone_info(
            address=env.message["prefix"]["host"]
        ).zone
    else:
        zonename = env.arg        

    import os.path
    zoneinfo = env.options["zoneinfo"]
    zonefile = os.path.join(zoneinfo, zonename)

    try: opt = api.clock.zoneinfo_offset(filename=zonefile)
    except Exception:
        env.reply("Unrecognised zone. Try using one of the TZ fields here:")
        env.reply("http://en.wikipedia.org/wiki/List_of_tz_database_time_zones")
    else:
        tz = round(opt.offset, 2)

        with env.database.context("timezones") as timezones:
            timezones[env.nick] = zonename

        # message = "Set your zone to %s, which is currently %s (%s)"
        message = "Set your TZ to %s; currently %s (UTC %s)"
        hours = round(tz / 3600, 3)
        hours = "+" + str(hours) if (hours >=0) else str(hours)
        hours = hours.rstrip("0").rstrip(".")
        env.reply(message % (zonename, opt.abbreviation, hours))

# @@ check nickname sanity
# IRC
@command
def to(env):
    "Send a message to another user"
    if not env.arg:
        return env.reply(to.__doc__)

    # import time
    # could be partly moved to api?
    recipient, message = env.arg.split(" ", 1)

    # check syntax of env.nick!
    # "self!" syntax to force a message to self
    if env.nick == recipient:
        return env.reply("You can tell yourself that")
    if env.options["nick"] == recipient:
        return env.reply("Understood")

    if not hasattr(input, "verb"):
        env.verb = None

    # @@ check nick format
    item = (int(time.time()), env.nick, env.verb, recipient, message)
    with env.database.context("messages") as messages:
        messages.setdefault(recipient, [])
        messages[recipient].append(item)

    env.reply("Will pass your message to %s" % recipient)
