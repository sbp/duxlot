# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

import duxlot

# Save PEP 3122!
if "." in __name__:
    from . import api
else:
    import api

# @@ Duplicated from standard.py
def zone_from_nick(env, nick):
    tz = env.database.cache.timezones.get(nick, None)
    if tz is None:
        return 0, "UTC"
    else:
        import os.path
        if not ("core" in env.options.completed): # @@ .groups
            return 0, "UTC"
        zoneinfo = env.options("core-zoneinfo")
        zonefile = os.path.join(zoneinfo, tz)

        try: opt = api.clock.zoneinfo_offset(filename=zonefile)
        except Exception:
            return 0, "UTC"
        return opt.offset, opt.abbreviation

@duxlot.startup
def cache_data(public):
    # @@ could this be even faster?
    # @@ needs to be anywhere that api is used!
    api.clock.cache_timezones_data()
    api.unicode.cache_unicode_data()

@duxlot.startup
def create_api_commands(public):
    services = api.text()

    def takes(service, kind):
        if hasattr(service, "argument"):
            return kind == service.argument
        return False

    for name in services:
        if name == "name":
            continue

        def create(name):
            canonicalised = name.strip("_").replace("_", "-")

            @duxlot.named(canonicalised)
            def api_command(env):
                if "limit" in env:
                    limit = env.limit
                else:
                    limit = 360

                arg = env.arg
                if (not arg) and takes(services[name], "link"):
                    if env.sender in env.database.cache.links:
                        arg = env.database.cache.links[env.sender]

                if takes(services[name], "tz"):
                    a, b = zone_from_nick(env, env.nick)
                    arg = ":%s :%s %s" % (a, b, arg)

                # @@ Service type? (irc, web, etc.)
                text = services[name](
                    text=arg,
                    maximum={
                        "bytes": limit,
                        "lines": 3
                    }
                )

                found_links = api.regex_link.findall(text)
                if found_links:
                    with env.database.context("links") as links:
                        links[env.sender] = found_links.pop()

                text = text.rstrip("\n")
                for line in text.split("\n"):
                    env.say(line)
            api_command.__doc__ = services[name].__doc__
        create(name)
