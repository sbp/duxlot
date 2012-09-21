# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

import time
import duxlot

# Save PEP 3122!
if "." in __name__:
    from . import api
else:
    import api

command = duxlot.command
event = duxlot.event

### Utilities ###

def zone_from_nick(env, nick):
    tz = env.database.cache.timezones.get(nick, None)
    if tz is None:
        return 0, "UTC"
    else:
        import os.path
        zoneinfo = env.options("core-zoneinfo")
        zonefile = os.path.join(zoneinfo, tz)

        try: opt = api.clock.zoneinfo_offset(filename=zonefile)
        except Exception:
            return 0, "UTC"
        return opt.offset, opt.abbreviation


### Named ###

# @@ .test-error
# @@ .test-timeout
# @@ .test-undocumented

@command
def ask(env):
    "Ask another user an enquiry"
    env.verb = "ask"
    to(env)

@command
def attributes(env):
    "Discover which attributes are available to internal functions"
    env.say("env: " + ", ".join(env().keys()))

@command
def _in(env):
    "Schedule a reminder to be sent after a specified time period"
    if not env.arg:
        return env.reply(_in.__doc__)

    opt = api.clock.periods_unixtime(text=env.arg)
    if not opt.seconds:
        return env.reply("Couldn't understand your duration. Use units?")

    if opt.remainder:
        text = env.nick + ": " + opt.remainder
    else:
        text = env.nick + "!"
    env.schedule(opt.unixtime, "msg", env.sender, text)

    # @@ needs to use the time zone *at opt.unixtime*, not current!
    offset, abbreviation = zone_from_nick(env, env.nick)
    phrase = api.clock.duration_phrase(
        tz=abbreviation,
        seconds=opt.seconds,
        unixtime=opt.unixtime,
        offset=offset
    )
    env.reply("Will remind %s" % phrase)

# env, kind of
# @@ Could be an api.text command
@command
def maximum(env):
    "Discover the maximum number of byte content that can be sent per message"
    if not "limit" in env:
        return env.say("I don't know the text limit at the moment, sorry")
    message = "The maximum length text I can send here is %s bytes"
    env.say(message % env.limit)

#        send(".noop")
#        receive("This will time out")

@command
def network_bytes(env):
    "Show input argument as python bytes representation"
    # @@ this is giving a space prefix
    command_size = len(env.prefix + "network-bytes")
    octets = env.message["parameters_octets"][1]
    octets = octets[command_size + 1:]
    env.reply(repr(octets))

# @@ or just "link"
@command
def noted_link(env):
    "Show currently noted link from this channel"
    # @@ not set up with .title yet?
    link = env.database.cache.links.get(env.sender)
    if link:
        env.reply(link)
    else:
        env.reply("No link found for here")

@command
def parsed_message(env):
    "Show parsed input message"
    env.reply(repr(env.message))

# make admin?
@command
def reload(env):
    "Reload all commands and services"
    env.task("reload", env.sender, env.nick)

# @@ This is just a debug command
@command
def schedule(env):
    "Schedule an event"
    # @@ database.timezones
    if not env.arg:
        return env.reply(schedule.__doc__)

    t, text = env.arg.split(" ", 1)
    t = float(t)
    # env.schedule(t, env.sender, env.nick, text)
    env.schedule(t, "msg", env.sender, env.nick + ": " + text)
    env.reply("Scheduled")

# @@ test to make sure the right time is given!
@command
def seen(env):
    "Find out whether somebody has been around recently"
    if not env.arg:
        return env.say(seen.__doc__)

    if env.arg == env.options("nick"):
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

# @@ a check that commands are covered here
@command
def stats(env):
    "Display information about the most used commands"
    usage = env.database.cache.usage

    usage = sorted(((b, a) for (a, b) in usage.items()), reverse=True)
    usage = list(usage)[:10]
    usage = ["%s (%s)" % (b, a) for (a, b) in usage]
    env.reply("Top used commands: " + ", ".join(usage))

@command
def tell(env):
    "Tell another user a message"
    # Inspired by Monty, by Paul Mutton
    # http://www.jibble.org/
    env.verb = "tell"
    to(env)

@command
def test_error(env):
    "Attempt to divide one by zero"
    1/0

# @@ <sbp> ..timer g
# <duxlot[t?]> sbp: http://en.wikipedia.org/wiki/G-force
# <duxlott> sbp: Took 0.52 seconds
# COMPLEX!
@command
def timer(env):
    "Time how long it takes to run another unparametric command"
    if not env.arg:
        return env.reply(timer.__doc__)
    if " " in env.arg:
        return env.reply("Command must not be parametric")
        # not only that, but the command must also ignore parameters...
    if env.arg == "timer":
        return env.reply("That would take too long")

    cmd = duxlot.commands.get(env.arg)
    if not cmd:
        return env.reply("No such command: \"%s\"" % env.arg[:32]) # @@

    before = time.time()
    cmd(env)
    after = time.time() - before
    env.reply("Took %s seconds" % round(after, 3))

# @@ move bits of this to api?
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
    zoneinfo = env.options("core-zoneinfo")
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
@command
def to(env):
    "Send a message to another user"
    if not env.arg:
        return env.reply(to.__doc__)

    # could be partly moved to api?
    recipient, message = env.arg.split(" ", 1)

    # check syntax of env.nick!
    # "self!" syntax to force a message to self
    if env.nick == recipient:
        return env.reply("You can tell yourself that")
    if env.options("nick") == recipient:
        return env.reply("Understood")

    if not hasattr(input, "verb"):
        env.verb = None

    # @@ check nick format
    item = (int(time.time()), env.nick, env.verb, recipient, message)
    with env.database.context("messages") as messages:
        messages.setdefault(recipient, [])
        messages[recipient].append(item)

    env.reply("Will pass your message to %s" % recipient)

@command
def val(env):
    "Deprecated: Use i-love-the-w3c instead"
    redirect = "i-love-the-w3c"
    env.reply("Command renamed to %s%s" % (env.prefix, redirect))

@command
def weather(env):
    "Redirect to metar"
    redirect = "metar"
    env.reply("Perhaps you meant %s%s" % (env.prefix, redirect))

@command
def zoneinfo_offset(env):
    # @@ no documentation, no args gives weird
    import os.path
    zoneinfo = env.options("zoneinfo")
    zonefile = os.path.join(zoneinfo, env.arg)
    opt = api.clock.zoneinfo_offset(filename=zonefile)
    env.reply("%s (%s)" % (opt.offset, opt.abbreviation))


### Events ###

# 1st

@event("1st")
def startup(env):
    # @@ limit timezones to a subset of seen
    for name in ("seen", "links", "messages", "timezones"):
        env.database.init(name, {})

# PRIVMSG

@event("PRIVMSG")
def privmsg_event(env):
    ### Send any outstanding user messages ###
    if env.nick in env.database.cache.messages:
        nick_tells = env.database.cache.messages[env.nick]
        if nick_tells:
            for t, nick, verb, recipient, message in nick_tells:
                datetime = api.clock.datetime_utc(unixtime=t)
                datetime = datetime[:-3] + "Z"
                date = api.clock.date_utc()
                if datetime.startswith(date):
                    datetime = datetime[len(date):].lstrip()

                if verb:
                    args = (recipient, datetime, nick, verb, recipient, message)
                    env.say("%s: %s <%s> %s %s %s" % args)
                else:
                    args = (recipient, datetime, nick, recipient, message)
                    env.say("%s: %s <%s> %s: %s" % args)
                # print times properly with respect to recipient currently

        with env.database.context("messages") as messages:
            del messages[env.nick]

    ### Respond to interjections ###
    if env.text == (env.options("nick") + "!"):
        env.say(env.nick + "!")

    ### Respond to prefix enquiries ###
    p_commands = {
        env.options("nick") + ": prefix",
        env.options("nick") + ": prefix?"
    }
    if env.text in p_commands:
        env.reply("Current prefix for here is \"%s\"" % env.prefix)

    ### Note channel links ###
    found_links = api.regex_link.findall(env.text)
    if found_links:
        with env.database.context("links") as links:
            links[env.sender] = found_links.pop()

    ### Note nicknames in seen database ###
    if env.sender.startswith("#"):
        private = set(env.options("core-private"))
        if not (env.sender in private):
            t = time.time()
            with env.database.context("seen") as seen:
                seen[env.nick] = (t, env.sender)

### Other ###

@duxlot.startup
def startup(public):
    if "core" in public.options.completed:
        return

    group = public.options.group
    option = public.options.option

    @group("core")
    class private(option):
        default = []
        types = {list}

    @group("core")
    class zoneinfo(option):
        default = "/usr/share/zoneinfo"

    public.options.complete("core")
