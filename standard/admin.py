# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

import duxlot

command = duxlot.command

# @@ more admin- prefixes

@command
def admin(env):
    # this should be an administrative command
    # show whether the user, or the arg nick, is an admin
    ...

@command
def channel_prefix(env):
    "Set the command prefix for a specific channel"
    if env.admin:
        if not (" " in env.arg):
            return env.reply("Usage: channel-prefix #channel <pfx>")

        channel, prefix = env.arg.split(" ", 1)
        channels = env.options("prefix", "channels")
        channels[channel] = prefix

        env.options.put("prefix", channels)
        env.reply("Set prefix for %s to %r" % (channel, prefix))

@command
def commands(env):
    "Output all commands and descriptions to a local file"
    if env.owner:
        def document(filename, named):
            import os.path
            filename = os.path.expanduser(filename)

            # with env.lock:
            with duxlot.filesystem.open(filename, "w", encoding="utf-8") as w:
                for name, function in sorted(named.items()):
                    w.write("." + name + "\n")
        
                    if hasattr(function, "__doc__") and function.__doc__:
                        w.write(function.__doc__ + "\n\n")
                    else:
                        w.write("ERROR: NO DOCUMENTATION!\n\n")

        try: document("~/.duxlot-commands", duxlot.commands)
        except (IOError, OSError) as err:
            env.reply("Error: " + str(err))
        else:
            env.reply("Written to ~/.duxlot-commands")

@command
def database_export(env):
    "Export part of the bot's persistent database"
    if env.owner and env.private:
        name = env.database.export(env.arg)
        env.reply("Exported \"%s\" to \"%s\"" % (env.arg, name))

@command
def database_load(env):
    "Load a database"
    if env.owner:
        data = env.database.load(env.arg)
        env.reply(repr(data))

@command
def join(env):
    "Command the bot to join a new channel"
    if env.admin:
        channels = env.options("start channels")
        if not (env.arg in channels):
            channels.append(env.arg)
            env.options.put("start channels", channels)

@command
def me(env):
    "Command the bot to perform an action message"
    if env.admin and env.private:
        recipient, text = env.arg.split(" ", 1)
        text = "\x01ACTION %s\x01" % text
        env.send("PRIVMSG", recipient, text)

@command
def msg(env):
    "Command the bot to send a message"
    if env.admin and env.private:
        recipient, text = env.arg.split(" ", 1)
        env.send("PRIVMSG", recipient, text)

@command
def nick(env):
    "Change the nickname of the bot"
    if env.owner and env.private:
        env.send("NICK", env.arg)

@command
def noted_links(env):
    "Show currently noted links from all channels"
    if env.admin and env.private:
        env.say(str(env.database.cache.links))

@command
def part(env):
    "Command the bot to part a channel"
    # @@ do proper env.options stuff!
    if env.admin:
        env.send("PART", env.arg)

@command
def pids(env):
    "Show the PIDs for the various processes"
    if env.owner and env.private:
        env.task("pids", env.sender, env.nick)

@command
def prefix(env):
    "Set the command prefix for all channels"
    if env.admin:
        current = env.options("prefix")
        if isinstance(current, str):
            env.options.put("prefix", env.arg)
        elif isinstance(current, list):
            current[""] = env.arg
            env.options.put("prefix", current)
        else:
            return env.reply("Error: prefix data is corrupt")

        env.reply("Set prefix for all channels to %r" % env.arg)

@command
def prefixes(env):
    "Show all prefixes used across all channels for all named commands"
    if env.admin:
        prefixes = env.options("prefix", "channels")
        prefixes = sorted(prefixes.items())
        p = ["%r %s" % (b, ("on " + a) if a else "by default")
            for a, b in prefixes]
        env.reply(", ".join(p))

@command
def processes(env):
    "Show the number of processes running, and their names"
    if env.admin: 
        env.task("processes", env.sender, env.nick)
    else:
        env.reply("That's an admin-only feature")
        # or, Ask an admin to do that

# @@ temp-admin?

@command
def quit(env):
    "Request the bot to quit from the server and exit"
    if env.credentials("owner", "adminchan"):
        env.task("quit", env.nick)

@command
def restart(env):
    "Restart the bot"
    if env.owner:
        env.task("restart")

@command
def service(env):
    "Display the results of an internal service call"
    if not env.arg:
        return env.reply(service.__doc__)

    if env.admin:
        import json
        service_name, json_data = env.arg.split(" ", 1)
    
        kargs = json.loads(json_data)
        o = api.services_manifest[service_name](**kargs)
        try: env.reply("JSON: " + json.dumps(o()))
        except Exception:
            env.reply("Non-JSON: " + repr(o))

@command
def supercombiner(env):
    "Print the supercombiner"
    if env.admin:
        env.say(api.unicode.supercombiner())
    else:
        env.reply("This is an admin-only feature")

@command
def test_hang(env):
    "Test a long hang, 120 seconds"
    if env.owner:
        import time
        env.say("Hanging...")
        time.sleep(120)
        env.say("Done!")

@command
def update_unicode_data(env):
    if env.owner:
        env.say("Updating unicodedata.pickle...")
        try: api.unicode.update_unicode_data()
        except Exception as err:
            env.reply("Error: " + str(err))
        else:
            env.reply("Done. You may now reload")

@command
def visit(env):
    "Command the bot to join a new channel"
    env.send("JOIN", env.arg)

### Events ###

# 433 (Nickname already in use)

@duxlot.event("433")
def nick_error2(env):
    if "address" in env.data:
        nick = env.message["parameters"][1]
        error = "Somebody tried to change my nick to %s," % nick
        error += " but that nick is already in use"
        env.msg(env.options("admin-owner"), error)

### Builders ###

# used by create_input
def administrators(options):
    permitted = set()
    owner = options("admin-owner")
    if owner:
        permitted.add(owner)
    admins = options("admin-users")
    if admins:
        permitted.update(set(admins))
    return permitted

@duxlot.builder
def build_admin(env):
    if env.event == "PRIVMSG":
        env.owner = env.nick == env.options("admin-owner")
        env.admin = env.nick in administrators(env.options) # @@!
        env.adminchan = env.sender in env.options("admin-channels")
    
        def credentials(person, place):
            person_okay = {
                "owner": env.owner,
                "admin": env.owner or env.admin
            #   "anyone": True # @@ for anyone + adminchan
            }.get(person, False)
    
            place_okay = {
                "anywhere": True,
                "adminchan": env.adminchan or env.private,
                "private": env.private
            }.get(place, False)
    
            return person_okay and place_okay
        env.credentials = credentials

    return env

@duxlot.startup
def startup(public):
    if "admin" in public.options.completed:
        return

    group = public.options.group
    option = public.options.option

    @group("admin")
    class channels(option):
        default = []
        types = {list}

    @group("admin")
    class owner(option):
        ...

    @group("admin")
    class users(option):
        default = []
        types = {list}

    public.options.complete("admin")
