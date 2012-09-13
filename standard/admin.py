# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

import duxlot

command = duxlot.command

@command
def admin(env):
    # this should be an administrative command
    # show whether the user, or the arg nick, is an admin
    ...

@command
def commands(env):
    "Output all commands and descriptions to a local file"
    if env.owner:
        def document(filename, named):
            import os.path
            filename = os.path.expanduser(filename)

            with env.lock:
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
        env.send("JOIN", env.arg)

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
    if env.admin:
        env.send("PART", env.arg)

@command
def prefix(env):
    "Change the prefix used before named commands"
    if env.admin:
        if env.arg.startswith("#") and (" " in env.arg):
            channel, prefix = env.arg.split(" ", 1)
            # if not ("prefixes" in env.options["__options__"]):
            #     env.options["prefixes"] = {}
            prefixes = env.options["prefixes"]
            prefixes[channel] = prefix
            env.options["prefixes"] = prefixes
            env.reply("Okay, set prefix to \"%s\" for %s" % (prefix, channel))
        else:
            env.options["prefix"] = env.arg
            env.reply("Okay, set prefix to \"%s\"" % env.arg)
    elif env.arg:
        env.reply("Sorry, that's an admin-only feature!")

@command
def prefixes(env):
    "Show all prefixes used across all channels for all named commands"
    if env.admin:
        prefixes = env.options["prefixes"]
        prefixes["*"] = env.options["prefix"]
        p = ["%s: \"%s\"" % (a, b) for a, b in sorted(prefixes.items())]
        env.reply(", ".join(p))
    else:
        env.reply("Sorry, that's an admin-only feature!")

@command
def processes(env):
    "Show the number of processes running, and their names"
    if env.admin: 
        env.schedule((0, "processes", env.sender, env.nick))
    else:
        env.reply("That's an admin-only feature")
        # or, Ask an admin to do that

# @@ temp-admin?

@command
def quit(env):
    "Request the bot to quit from the server and exit"
    if env.credentials("owner", "adminchan"):
        env.schedule((0, "quit", env.nick))

@command
def reload2(env):
    "Reload all commands and services"
    if env.credentials("admin", "adminchan"):
    # if env.admin: # @@ private, admin-channel only?
        # could send reloading first, then join send queue
        env.reply("Okay, reloading...")
        env.sent()
        env.schedule((0, "reload", env.sender, env.nick))
    else:
        env.reply("That's an admin-only feature")
        # or, Ask an admin to do that

@command
def restart(env):
    "Restart the bot"
    if env.owner:
        env.schedule((0, "restart",))

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

### Events ###

# 433 (Nickname already in use)

@duxlot.event("433")
def nick_error2(env):
    if "address" in env.data:
        nick = env.message["parameters"][1]
        error = "Somebody tried to change my nick to %s," % nick
        error += " but that nick is already in use"
        env.msg(env.options["owner"], error)

### Builders ###

# used by create_input
def administrators(options):
    permitted = set()
    owner = options["owner"]
    if owner:
        permitted.add(owner)
    admins = options["admins"]
    if admins:
        set.update(set(admins))
    return permitted

@duxlot.builder
def build_admin(env):
    if env.event == "PRIVMSG":
        env.owner = env.nick == env.options["owner"]
        env.admin = env.nick in administrators(env.options) # @@!
        env.adminchan = env.sender in env.options["adminchans"]
    
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
