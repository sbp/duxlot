# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

import duxlot

command = duxlot.command

@command
def admin(irc, input):
    # this should be an administrative command
    # show whether the user, or the arg nick, is an admin
    ...

@command
def commands(irc, input):
    "Output all commands and descriptions to a local file"
    if input.owner:
        def document(filename, named):
            import os.path
            filename = os.path.expanduser(filename)

            with irc.lock:
                with open(filename, "w", encoding="utf-8") as f:
                    for name, function in sorted(named.items()):
                        w.write("." + name + "\n")
            
                        if hasattr(function, "__doc__") and function.__doc__:
                            w.write(function.__doc__ + "\n\n")
                        else:
                            w.write("ERROR: NO DOCUMENTATION!\n\n")

        try: document("~/.duxlot-commands", duxlot.commands)
        except (IOError, OSError) as err:
            irc.reply("Error: " + str(err))
        else:
            irc.reply("Written to " + input.arg)

@command
def database_export(irc, input):
    "Export part of the bot's persistent database"
    if input.owner and input.private:
        name = irc.database.export(input.arg)
        irc.reply("Exported \"%s\" to \"%s\"" % (input.arg, name))

@command
def database_load(irc, input):
    "Load a database"
    if input.owner:
        data = irc.database.load(input.arg)
        irc.reply(repr(data))

@command
def join(irc, input):
    "Command the bot to join a new channel"
    if input.admin:
        irc.send("JOIN", input.arg)

@command
def me(irc, input):
    "Command the bot to perform an action message"
    if input.admin and input.private:
        recipient, text = input.arg.split(" ", 1)
        text = "\x01ACTION %s\x01" % text
        irc.send("PRIVMSG", recipient, text)

@command
def msg(irc, input):
    "Command the bot to send a message"
    if input.admin and input.private:
        recipient, text = input.arg.split(" ", 1)
        irc.send("PRIVMSG", recipient, text)

@command
def nick(irc, input):
    "Change the nickname of the bot"
    if input.owner and input.private:
        irc.send("NICK", input.arg)

@command
def noted_links(irc, input):
    "Show currently noted links from all channels"
    if input.admin and input.private:
        irc.say(str(irc.database.cache.links))

@command
def part(irc, input):
    "Command the bot to part a channel"
    if input.admin:
        irc.send("PART", input.arg)

@command
def prefix(irc, input):
    "Change the prefix used before named commands"
    if input.admin:
        if input.arg.startswith("#") and (" " in input.arg):
            channel, prefix = input.arg.split(" ", 1)
            # if not ("prefixes" in irc.options["__options__"]):
            #     irc.options["prefixes"] = {}
            prefixes = irc.options["prefixes"]
            prefixes[channel] = prefix
            irc.options["prefixes"] = prefixes
            irc.reply("Okay, set prefix to \"%s\" for %s" % (prefix, channel))
        else:
            irc.options["prefix"] = input.arg
            irc.reply("Okay, set prefix to \"%s\"" % input.arg)
    elif input.arg:
        irc.reply("Sorry, that's an admin-only feature!")

@command
def prefixes(irc, input):
    "Show all prefixes used across all channels for all named commands"
    if input.admin:
        prefixes = irc.options["prefixes"]
        prefixes["*"] = irc.options["prefix"]
        p = ["%s: \"%s\"" % (a, b) for a, b in sorted(prefixes.items())]
        irc.reply(", ".join(p))
    else:
        irc.reply("Sorry, that's an admin-only feature!")

@command
def processes(irc, input):
    "Show the number of processes running, and their names"
    if input.admin: 
        irc.task(("processes", input.sender, input.nick))
    else:
        irc.reply("That's an admin-only feature")
        # or, Ask an admin to do that

# @@ temp-admin?

@command
def quit(irc, input):
    "Request the bot to quit from the server and exit"
    if input.credentials("owner", "adminchan"):
    # if input.owner and input.private:
        irc.send("QUIT", "%s made me do it" % input.nick)
        irc.sent()
        irc.task(("quit",))

@command
def reload(irc, input):
    "Reload all commands and services"
    if input.credentials("admin", "adminchan"):
    # if input.admin: # @@ private, admin-channel only?
        # could send reloading first, then join send queue
        irc.reply("Okay, reloading...")
        irc.sent()
        irc.task(("reload", input.sender, input.nick))
    else:
        irc.reply("That's an admin-only feature")
        # or, Ask an admin to do that

@command
def restart(irc, input):
    "Restart the bot"
    if input.owner:
        irc.task(("restart",))

@command
def service(irc, input):
    "Display the results of an internal service call"
    if not input.arg:
        return irc.reply(service.__doc__)

    if input.admin:
        import json
        service_name, json_data = input.arg.split(" ", 1)
    
        kargs = json.loads(json_data)
        o = api.services_manifest[service_name](**kargs)
        try: irc.reply("JSON: " + json.dumps(o()))
        except Exception:
            irc.reply("Non-JSON: " + repr(o))

@command
def supercombiner(irc, input):
    "Print the supercombiner"
    if input.admin:
        irc.say(api.unicode.supercombiner())
    else:
        irc.reply("This is an admin-only feature")

@command
def update_unicode_data(irc, input):
    if input.owner:
        irc.say("Updating unicodedata.pickle...")
        try: api.unicode.update_unicode_data()
        except Exception as err:
            irc.reply("Error: " + str(err))
        else:
            irc.reply("Done. You may now reload")
