# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

import duxlot

# Save PEP 3122!
if "." in __name__:
    from . import api
else:
    import api

command = duxlot.command

# @@ more admin- prefixes
# @@ .modules, for loaded modules

@command
def admin(env):
    # this should be an administrative command
    # show whether the user, or the arg nick, is an admin
    ...

# @@ temp-admin?

### Owner commands ###

E_ADMIN = "Only available to an admin"
E_ADMIN_PLACE = "Only available to an admin in an admin place"
E_ADMIN_PRIVATE = "Only available to an admin in private"
E_OWNER = "Only available to the owner"
E_OWNER_PLACE = "Only available to the owner in an admin place"
E_OWNER_PRIVATE = "Only available to the owner in private"

@command
def commands(env):
    "Output all commands and descriptions to a local file"
    if env.admin.owner and env.admin.place:
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
    elif env.admin.user:
        env.reply("This is an owner plus admin-place-only command")

@command
def database_export(env):
    "Export part of the bot's persistent database"
    if env.admin.owner and env.admin.place:
        name = env.database.export(env.arg)
        env.reply("Exported \"%s\" to \"%s\"" % (env.arg, name))
    elif env.admin.user:
        env.reply("This is an owner plus admin-place-only command")

@command
def database_load(env):
    "Load a database"
    if env.admin.owner and env.admin.place:
        data = env.database.load(env.arg)
        env.reply(repr(data))
    elif env.admin.user:
        env.reply("This is an owner and admin-place-only command")

@command
def modules(env):
    "Show currently loaded modules"
    if env.admin.owner and env.admin.place:
        env.reply(repr(env.data.modules))
    elif env.admin.user:
        env.reply("This is an owner and admin-place-only command")

@command
def nick(env):
    "Change the nickname of the bot"
    if env.admin.owner and env.admin.place:
        env.send("NICK", env.arg)
    elif env.admin.user:
        env.reply("This is an owner plus admin-place-only command")

@command
def pids(env):
    "Show the PIDs for the various processes"
    if env.admin.owner and env.private:
        env.task("pids", env.sender, env.nick)
    elif env.admin.user and env.admin.place:
        env.reply("This is an owner plus private-only command")

@command
def quit(env):
    "Request the bot to quit from the server and exit"
    if env.admin.owner and env.admin.place:
        env.task("quit", env.nick)
    elif env.admin.user and env.admin.place:
        env.reply("This is an owner-only command")

@command
def restart(env):
    "Restart the bot"
    if env.admin.owner and env.admin.place:
        env.task("restart")
    elif env.admin.user and env.admin.place:
        env.reply("This is an owner-only command")

@command
def test_hang(env):
    "Test a long hang, 120 seconds"
    if env.admin.owner and env.admin.place:
        import time
        env.say("Hanging...")
        time.sleep(120)
        env.say("Done!")
    elif env.admin.user and env.admin.place:
        env.reply("This is an owner and admin-place-only command")

@command
def update_unicode_data(env):
    if env.admin.owner and env.admin.place:
        env.say("Updating unicodedata.pickle...")
        try: api.unicode.update_unicode_data()
        except Exception as err:
            env.reply("Error: " + str(err))
        else:
            env.reply("Done. You may now reload")
    elif env.admin.user and env.admin.place:
        env.reply("This is an owner and admin-place-only command")

### Admin commands ###

@command
def channel_prefix(env):
    "Set the command prefix for a specific channel"
    if env.admin.user:
        if not (" " in env.arg):
            return env.reply("Usage: channel-prefix #channel <pfx>")
        channel, prefix = env.arg.split(" ", 1)

        channels = env.options("prefix", "channels")
        channels[channel] = prefix
        env.options.put("prefix", channels)

        env.reply("Set prefix for %s to %r" % (channel, prefix))
    else:
        env.reply("This is an admin-only command")

@command
def join(env):
    "Command the bot to join a new channel"
    if env.admin.user and env.admin.place:
        channels = env.options("start-channels")
        if not (env.arg in channels):
            channels.append(env.arg)
            env.options.put("start-channels", channels)
            env.reply("Joined " + env.arg)

@command
def me(env):
    "Command the bot to perform an action message"
    if env.admin.user and env.private:
        recipient, text = env.arg.split(" ", 1)
        text = "\x01ACTION %s\x01" % text
        env.send("PRIVMSG", recipient, text)

@command
def msg(env):
    "Command the bot to send a message"
    if env.admin.user and env.private:
        recipient, text = env.arg.split(" ", 1)
        env.send("PRIVMSG", recipient, text)

@command
def noted_links(env):
    "Show currently noted links from all channels"
    if env.admin.user and env.private:
        env.say(str(env.database.cache.links))
    elif env.admin.user and env.admin.channel:
        env.reply("This is an admin plus private-only command")

@command
def part(env):
    "Command the bot to part a channel"
    # @@ do proper env.options stuff!
    if env.admin.user and env.admin.place:
        channels = env.options("start-channels")
        if env.arg in channels:
            channels.remove(env.arg)
            env.options.put("start-channels", channels)
            env.reply("Parted " + env.arg)
        else:
            env.send("PART", env.arg)
            env.reply("Parted " + env.arg)

@command
def prefix(env):
    "Set the command prefix for all channels"
    if env.admin.user:
        current = env.options("prefix")
        if isinstance(current, str):
            env.options.put("prefix", env.arg)
        elif isinstance(current, list):
            current[""] = env.arg
            env.options.put("prefix", current)
        else:
            return env.reply("Error: prefix data is corrupt")

        env.reply("Set prefix for all channels to %r" % env.arg)
    else:
        env.reply("This is an admin-only command")

@command
def prefixes(env):
    "Show all prefixes used across all channels for all named commands"
    if env.admin.user and env.admin.place:
        prefixes = env.options("prefix", "channels")
        prefixes = sorted(prefixes.items())
        p = ["%r %s" % (b, ("on " + a) if a else "by default")
            for a, b in prefixes]
        env.reply(", ".join(p))
    elif env.admin.user:
        env.reply("This is an admin and admin-place-only command")

@command
def processes(env):
    "Show the number of processes running, and their names"
    if env.admin.user:
        env.task("processes", env.sender, env.nick)
    else:
        env.reply("This is an admin-only command")
        # or, Ask an admin to do that

@command
def service(env):
    "Display the results of an internal service call"
    if not env.arg:
        return env.reply(service.__doc__)

    if env.admin.user and env.admin.place:
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
    if env.admin.user:
        env.say(api.unicode.supercombiner())
    else:
        env.reply("This is an admin-only command")

@command
def visit(env):
    "Command the bot to visit a new channel temporarily"
    if env.admin.user and env.admin.place:
        env.send("JOIN", env.arg)
    elif env.admin.user:
        env.reply("This is an admin and admin-place-only command")


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

# @duxlot.irc.augment?
@duxlot.builder
def build_admin(env):
    if env.event == "PRIVMSG":
        env.admin = duxlot.Storage()

        env.admin.owner = env.nick == env.options("admin-owner")
        admin_user =(env.nick in env.options("admin-users"))

        env.admin.user = env.admin.owner or admin_user
        env.admin.channel = env.sender in env.options("admin-channels")
        env.admin.place = env.private or env.admin.channel

    return env


### Startup ###

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
