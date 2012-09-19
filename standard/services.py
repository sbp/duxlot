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

web_services_manifest = {}

@command
def load_services(env):
    "Load the new services"
    global web_services_manifest
    web_services_manifest = api.services.manifest()
    env.database.dump("services", web_services_manifest)
    env.reply("%s services loaded" % len(web_services_manifest))

@command
def services(env):
    "Show the number of loaded services"
    env.reply("%s services available" % len(web_services_manifest))

@duxlot.startup
def create_web_services(public):
    global web_services_manifest

    public.database.init("services", {}) # @@ or just load with default
    web_services_manifest = public.database.cache.services
    items = web_services_manifest.items()

    for command_name, url in items:
        if command_name in {"py", "wa"}:
            continue

        def create(command_name, url):
            if command_name in duxlot.commands:
                # @@ Need a better services list
                # print("Warning: Skipping duplicate: %s" % command_name)
                return

            @duxlot.named(command_name)
            def service(env):
                kargs = {
                    "url": service.url,
                    "arg": env.arg,
                    "nick": env.nick,
                    "sender": env.sender
                }
                line = api.services.query(**kargs)
                if line:
                    env.say(line[:510])
            service.__doc__ = "Web service: %s" % url
            service.url = url
        create(command_name, url)
