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

# def administrative(options, input):
#     if env.admin and (env.sender in options

def zone_from_nick(env, nick):
    tz = env.database.cache.timezones.get(nick, None)
    if tz is None:
        return 0, "UTC"
    else:
        import os.path
        zoneinfo = env.options["zoneinfo"]
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
def about(env):
    "Give information about a named bot command"
    if not env.arg:
        return env.reply(about.__doc__)

    if env.arg in duxlot.commands:
        function = duxlot.commands[env.arg]
        if hasattr(function, "__doc__") and function.__doc__:
            env.reply(function.__doc__)
        else:
            env.reply("That command has no documentation")
    else:
        env.reply("Couldn't find that command")

@command
def attributes(env):
    "Discover which attributes are available to internal functions"
    # @@ this is broken, input doesn't work
    env.say("env: " + ", ".join(env().keys()))

@command
def beats(env):
    "Show current time in Swatch internet beats"
    opt = api.clock.beats()
    env.reply(opt.beats)

# @@ .bing [...]vzmvnncvz
# @@ <duxlot> Python Error. IncompleteRead(27254 bytes read): standard.py:101 bing(...) ?
@command
def bing(env):
    "Search for a phrase on Bing"
    if not env.arg:
        return env.reply(bing.__doc__)

    try: url = api.search.bing(phrase=env.arg)
    except api.Error:
        return env.reply("Couldn't find any results")

    if isinstance(url, str):
        env.reply(url)
    else:
        env.reply("No results found")

    # @@ could persist this
    # @@ make sends monitorable
    with env.database.context("links") as links:
        links[env.sender] = url

# @@ snack
@command
def botsnack(env):
    "Give the bot a botsnack"
    env.say(":)")

# @@ doesn't work in console
@command
def bytes(env):
    "Show input argument as python bytes representation"
    # @@ this is giving a space prefix
    command_size = len(env.prefix + "bytes")
    octets = env.message["parameters_octets"][1]
    octets = octets[command_size + 1:]
    env.reply(repr(octets))

@command
def c(env):
    "Calculate an expression using Google calculator"
    if not env.arg:
        return env.reply(c.__doc__)

    try: calculation = api.google.calculator(expression=env.arg)
    except api.Error as err:
        return env.reply(str(err))

    if "response" in calculation:
        env.say(calculation.response)
    else:
        env.say("Error")

@command
def calc(env):
    "Calculate an expression using Google calculator"
    c(env)

@command
def chars(env):
    "Unicode characters grep"
    # @@ better doc
    if not env.arg:
        return env.reply(ucg.__doc__)

    flag, arg = api.irc.optflag(arg=env.arg)
    if not arg:
        return env.reply("Need something to search for")

    try: result = api.unicode.character_grep(search=arg, categories=flag)
    except api.Error as err:
        return env.reply(str(err))
    env.reply(result)

# @@ zone_from_nick is IRC bound...
@command
def date(env):
    "Display the current date in UTC"
    offset, abbreviation = zone_from_nick(env, env.nick)
    message = api.clock.format_datetime(format="%Y-%m-%d", offset=offset)
    env.say(message)

@command
def decode(env):
    "Decode text containing HTML entities"
    if not env.arg:
        return env.reply(decode.__doc__)

    text = api.html.decode_entities(html=env.arg)
    env.say(text)

@command
def duck(env):
    "Search for a phrase on DuckDuckGo"
    if not env.arg:
        return env.reply(duck.__doc__)

    try: url = api.search.duck(phrase=env.arg)
    except api.Error as err:
        return env.reply(str(err))

    env.reply(url)

    with env.database.context("links") as links:
        links[env.sender] = url

# @@ inamidst.com, without http:// and /
@command
def encoding(env):
    "Determine the encoding of a web page"
    if not env.arg:
        example = "Example: %sencoding http://sbp.so/"
        return env.reply(example % env.prefix)

    opt = api.web.request(url=env.arg)
    if "encoding" in opt:
        summary = opt.encoding
        if "encoding_source" in opt:
            summary += " (%s)" % opt.encoding_source
        env.reply(summary)
    elif "error" in opt:
        env.reply("Error: %s" % opt.error)
    else:
        env.reply("Couldn't determine the encoding")

@command
def error_test(env):
    "Attempt to divide one by zero"
    1/0

# @@ .ety love - random words?
@command
def ety(env):
    "Display the etymology of a term from Etymonline"
    # @@ .ety love doesn't work
    if not env.arg:
        example = "Example: %setymology frog"
        return env.reply(example % env.prefix)

    limit = env().get("limit", 360)

    try: opt = api.word.etymology(term=env.arg, limit=limit)
    except api.Error as err:
        msg = "Nothing found. Try http://etymonline.com/search.php?term=%s"
        return env.say (msg % env.arg)

    if "sentence" in opt:
        env.say('"%s" - %s' % (opt.sentence, opt.url))
    else:
        env.say("?")

@command
def follow(env):
    "Follow web page redirect and report the destination"
    if not env.arg:
        example = "Example: %sfollow http://sbp.so/p"
        return env.reply(example % env.prefix)

    opt = api.web.request(
        method="HEAD",
        follow=True,
        url=env.arg
    )

    if "url" in opt:
        env.reply(opt.url)
    elif "error" in opt:
        env.reply("Error: %s" % opt.error)
    else:
        env.reply("Couldn't follow that url")

@command
def g(env):
    "Search for a phrase on Google"
    if not env.arg:
        return env.reply(g.__doc__)

    try: url = api.google.search_api(phrase=env.arg)
    except api.Error as err:
        return env.reply(str(err))

    env.reply(url)

    # @@ could persist this
    with env.database.context("links") as links:
        links[env.sender] = url

@command
def gc(env):
    "Show the Google search result count of a phrase"
    if not env.arg:
        return env.reply(gc.__doc__)

    flag, arg = api.irc.optflag(arg=env.arg)
    try: count = api.google.count(phrase=arg, method=flag)
    except api.Error as err:
        return env.reply(str(err))            

    if flag in {None, "", "*", "all"}:
        # @@ only add the arg if there's been another recent gc
        env.say("%s - %s" % (count, arg))
    else:
        env.say("%s: %s" % (arg, count))

@command
def gcs(env):
    "Show the Google search result counts of up to six terms inclusive"
    # broken: §gcs [hello nsh] "what's up?" [this is a demo] of gcs
    if not env.arg:
        return env.reply(gcs.__doc__)

    flag, arg = api.irc.optflag(arg=env.arg)

    text = "[api] " if (not flag) else ""
    method = "api" if (not flag) else flag

    try: text += api.google.counts_api(terms=arg, method=method)
    except api.Error as err:
        return env.reply(str(err))            
    env.say(text)

@command
def gd(env):
    "Get a definition using Google Dictionary"
    # @@ .gd define is a bit spacey
    if not env.arg:
        return env.reply(gd.__doc__)

    try: definition = api.google.dictionary(term=env.arg)
    except api.Error as err:
        return env.reply(str(err))

    env.reply(definition)

@command
def head(env):
    "Get information about a web page using an HTTP HEAD request"
    if not env.arg:
        return env.reply(head.__doc__)

    # @@ getting ETag won't work
    header = None
    if " " in env.arg:
        a, b = env.arg.split(" ", 1)
        if "." in a:
            url, header = a, b
        else:
            header, url = a, b
    else:
        url = env.arg

    opt = api.web.head_summary(url=url)
    if header:
        if header.lower() in opt.headers:
            return env.reply(opt.headers[header.lower()])
        else:
            return env.reply("No header %s in %s" % (header, url))

    env.reply(opt.summary)

# @@ not bot. make this better
@command
def help(env):
    "Provide details about the bot"
    if env.arg:
        about(env)
    else:
        message = "I am %s. Details: http://inamidst.com/duxlot/"
        env.say(message % env.options["nick"])

# @@ filetype, site
@command
def img(env):
    "Search for an image on Google Image Search"
    if not env.arg:
        return env.reply(img.__doc__)

    try: url = api.google.image(phrase=env.arg)
    except api.Error as err:
        return env.reply(str(err))

    env.reply(url)
    import urllib.parse
    arg = urllib.parse.quote(env.arg)
    env.say("More: http://google.com/images?q=%s" % arg)

# IRC
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
    env.schedule((opt.unixtime, "msg", env.sender, text))

    # @@ needs to use the time zone *at opt.unixtime*, not current!
    offset, abbreviation = zone_from_nick(env, env.nick)
    phrase = api.clock.duration_phrase(
        tz=abbreviation,
        seconds=opt.seconds,
        unixtime=opt.unixtime,
        offset=offset
    )
    env.reply("Will remind %s" % phrase)

@command
def ip_time(env):
    "Show the current time guessed for the IP address given"
    # @@ mix with database.timezones
    if not env.arg:
        return env.reply(ip_time.__doc__)

    try: dt = api.geo.timezone(ip=env.arg)
    except api.Error as err:
        return env.reply(str(err))
    env.reply(dt)

@command
def _len(env):
    "Show the length of the input in characters and utf-8 bytes"
    characters = len(env.arg)
    bytes = len(env.arg.encode("utf-8"))
    env.reply("%s chars, %s bytes (utf-8)" % (characters, bytes))

@command
def leo(env):
    "Search for a term in the LEO German Dictionary"
    # @@ empty results are formatted weirdly
    if not env.arg:
        return env.reply(leo.__doc__)

    try: opt = api.word.leo(term=env.arg)
    except api.Error as err:
        return env.reply(str(err))

    if not opt.text.strip():
        return env.reply("Nothing found at " + opt.url)

    env.reply(opt.text + " — " + opt.url)

@command
def load_services(env):
    "Load the new services"
    global web_services_manifest
    web_services_manifest = api.services.manifest()
    env.database.dump("services", web_services_manifest)
    env.reply("%s services loaded" % len(web_services_manifest))

@command
def mangle(env):
    "Put a phrase through the multiple translation mangle"
    if not env.arg:
        return env.reply(mangle.__doc__)

    # import time
    # @@ this should be in api
    opt = duxlot.Storage()
    opt.source = "en"
    opt.text = env.arg
    for target in ("fr", "de", "es", "it", "ja", "en"): 
        opt.target = target
        opt = api.google.translate(**opt())

        opt.text = opt.translation
        opt.source = opt.target
        time.sleep(1/3)
    env.reply(opt.translation)

# env, kind of
@command
def maximum(env):
    "Discover the maximum number of byte content that can be sent per message"
    if not "limit" in env:
        return env.say("I don't know the text limit at the moment, sorry")
    message = "The maximum length text I can send here is %s bytes"
    env.say(message % env.limit)

@command
def metar(env):
    "Get a formatted METAR weather summary for an ICAO code"
    if not env.arg:
        example = "Example for London, Heathrow: %smetar EGLL"
        return env.reply(example % env.prefix)

    summary = api.weather.metar_summary(icao=env.arg)
    env.reply(summary)

@command
def news(env):
    "Search for a news article on Google News Search"
    if not env.arg:
        return env.reply(news.__doc__)

    try: url = api.google.news(phrase=env.arg)
    except api.Error as err:
        return env.reply(str(err))

    env.reply(url)
    import urllib.parse
    arg = urllib.parse.quote(env.arg)
    env.say("More: http://google.com/news?q=%s" % arg)

#        send(".noop")
#        receive("This will time out")

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
def npl(env):
    "Display the current time from NPL's SNTP server"
    # @@ database.timezones
    opt = api.clock.npl()
    env.say("%s - %s" % (opt.datetime, opt.server))

@command
def o(env):
    ":O"
    env.say(":O")

@command
def parse_irc_message(env):
    "Parse a raw IRC message into structured data"
    if not env.arg:
        return env.reply(parse_irc_message.__doc__)

    octets = env.arg.encode("utf-8")
    o = api.irc.parse_message(octets=octets)
    env.reply(str(o()))

@command
def ping(env):
    "There is no ping command"
    msg = "%s; nor can this be construed as a response"
    env.reply(msg % ping.__doc__)

@command
def py(env):
    "Evaluate a python expression using Google App Engine"
    if not env.arg:
        return env.reply(py.__doc__)

    url = "http://tumbolia.appspot.com/py/${args}"
    line = api.services.query(url=url, arg=env.arg)
    if line:
        env.say(line[:510])
    else:
        env.say("Sorry, no result!")

@command
def reload(env):
    "Reload all commands and services"
    env.sent()
    env.schedule((0, "reload", env.sender, env.nick))

@command
def rhymes(env):
    "Show some perfect rhymes of a word"
    try: text = api.word.rhymes(word=env.arg)
    except api.Error as err:
        env.reply("Error: " + str(err))
    else:
        env.reply(text)

@command
def search_trio(env):
    "Search Google, Bing, and DuckDuckGo, and compare the results"
    if not env.arg:
        return env.reply(search_trio.__doc__)

    result = api.search.trio(phrase=env.arg)
    env.reply(result)

@command
def services(env):
    "Show the number of loaded services"
    env.reply("%s services available" % len(web_services_manifest))

# @@ uses env.nick, not generic
@command
def snippets(env):
    "Search for snippets using the Google API"
    if not env.arg:
        return env.reply(snippets.__doc__)

    snippets = api.google.search_api_snippets(phrase=env.arg)
    limit = env().get("limit", 256)
    limit = limit - len(env.nick + ": ") - 128
    snippets = " / ".join(snippets)[:limit - 3] + "..."
    env.reply(snippets)

@command
def suggest(env):
    "Get suggestions using Google Suggest"
    if not env.arg:
        return env.reply(suggest.__doc__)

    # @@ quote(arg).replace('+', '%2B')
    url = "http://websitedev.de/temp-bin/suggest.pl?q=${args}"
    line = api.services.query(url=url, arg=env.arg)
    if line:
        env.say(line[:510])
    else:
        env.say("Sorry, no result!")

# @@ zone_from_nick
@command
def t(env):
    "Display the current date and time"
    # @@ database.timezones
    if not env.arg:
        fmt = "%d %b %Y, %H:%M:%S $TZ"
        offset, abbreviation = zone_from_nick(env, env.nick)
        dt = api.clock.format_datetime(
            format=fmt,
            offset=offset,
            tz=abbreviation
        )
        env.say(dt)

    # @@ upper...
    elif env.arg.upper() in api.clock.timezones_data:
        dt = api.clock.timezone_datetime(tz=env.arg.upper())
        env.say(dt) # @@ add the tz name?

    elif api.clock.data.regex_number.match(env.arg):
        offset = float(env.arg) if ("." in env.arg) else int(env.arg)
        dt = api.clock.offset_datetime(offset=offset)
        env.say(dt)

    elif api.clock.data.regex_zone.match(env.arg):
        unix_date(env)

    else:
        env.reply("Unknown format: %s" % env.arg)

@command
def thesaurus(env):
    "Show some synonyms of a word"
    try: text = api.word.thesaurus(word=env.arg)
    except api.Error as err:
        env.reply("Error: " + str(err))
    else:
        env.reply(text)

# @@ zone_from_nick
@command
def _time(env):
    "Display the current time in UTC"
    offset, abbreviation = zone_from_nick(env, env.nick)
    dt = api.clock.format_datetime(format="%H:%M:%S", offset=offset)
    env.say(dt)

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

# @@ check for double spaces, etc.

@command
def title(env):
    "Get the title of a web page"
    if not env.arg:
        if env.sender in env.database.cache.links:
            url = env.database.cache.links[env.sender]
            return env.reply(api.web.title(url=url, follow=True))
        return env.reply(title.__doc__)

    url = env.arg

    # @@ make this a general utility function
    if not "/" in url:
        url = url + "/"
    if not "://" in url:
        url = "http://" + url

    env.reply(api.web.title(url=url, follow=True))

@command
def tock(env):
    "Display the time from the USNO tock server"
    # @@ database.timezones
    opt = api.clock.tock()
    env.say("\"%s\" - %s" % (opt.date, opt.server))

@command
def tr(env):
    "Translate text from one language to another"
    if not env.arg:
        return env.reply(tr.__doc__)

    opt = duxlot.Storage()
    opt.source, arg = api.irc.optflag(arg=env.arg)
    opt.target, opt.text = api.irc.optflag(arg=arg)
    opt = api.google.translate(**opt())
    t = opt.translation[:-1] if opt.translation.endswith(".") else opt.translation
    msg = "%s (%s » %s). translate.google.com"
    env.reply(msg % (opt.translation, opt.source, opt.target))

@command
def tw(env):
    "Show a tweet"
    if not env.arg:
        return env.reply("Give me a link, a username, or a tweet id")

    def tweet(**kargs):
        try: return api.twitter.tweet(**kargs)
        except api.Error as err:
            return str(err)

    arg = env.arg
    if arg.startswith("@"):
        arg = arg[1:]

    if arg.isdigit():
        tweet = tweet(id=arg)
    elif api.regex_twitter_username.match(arg):
        tweet = tweet(username=arg)
    elif api.regex_twitter_link.match(arg):
        tweet = tweet(url=arg)
    else:
        return env.reply("Give me a link, a username, or a tweet id")

    env.say(tweet)

@command
def twitter(env):
    "Show a tweet"
    tw(env)

@command
def tz(env):
    "Convert a time in one time zone to another"
    if not env.arg:
        return env.reply(tz.__doc__)

    def usage():
        env.reply("The format is: HH:MM[:SS] ZONE in ZONE")

    if env.arg.count(" ") == 3:
        t, source_zone, verb, target_zone = env.arg.split(" ", 3)
    else:
        return usage()

    kargs = {"time": t, "source": source_zone, "target": target_zone}
    conversion = api.clock.timezone_convert(**kargs)
    if not "target_time" in conversion:
        return usage()

    source = "%s %s" % (conversion.source_time, conversion.source_name)
    target = "%s %s" % (conversion.target_time, conversion.target_name)

    env.say(source + " = " + target)

@command
def u(env):
    "Perform various unicode search functions"
    if not env.arg:
        return env.reply(u.__doc__)
    import re

    flag, arg = api.irc.optflag(arg=env.arg)

    regex_digit = re.compile("[0-9]")
    regex_hex = re.compile("(?i)^[0-9A-F]{2,6}$")
    regex_codepoint = re.compile(r"(?i)^(U\+|\\u)[0-9A-F]{2,6}$")
    regex_simple = re.compile(r"^[\x20-\x7E]+$")

    if flag and (not arg):
        ubc(env)
    elif len(arg) == 1:
        ubc(env)
    elif regex_codepoint.match(arg):
        ubcp(env)
    elif regex_digit.search(arg) and regex_hex.match(arg):
        ubcp(env)
    elif not regex_simple.match(arg):
        ubc(env)
    else:
        ubn(env)

@command
def ubc(env):
    "Give data about unicode characters"
    if not env.arg:
        return env.reply(ubc.__doc__)

    flag, arg = api.irc.optflag(arg=env.arg)
    if flag and (not arg):
        flag, arg = None, env.arg

    kargs = {"characters": arg, "form": flag}
    try: messages = api.unicode.by_character_formatted(**kargs)
    except api.Error as err:
        return env.reply(str(err))

    env.say(", ".join(messages))

@command
def ubcp(env):
    "Search for a unicode character by hexadecimal codepoint"
    if not env.arg:
        return env.reply(ubcp.__doc__)

    flag, arg = api.irc.optflag(arg=env.arg)
    if not arg:
        return env.reply("Need something to search for")

    for prefix in ("U+", "u+", r"\u"):
        if arg.startswith(prefix):
            arg = arg[2:] # update if adding a different length above
            break

    try: result = api.unicode.by_hexcp(hex=arg, categories=flag)
    except api.Error as err:
        return env.reply(str(err))

    codepoint, data = result
    args = (codepoint, data["name"], data["display"], data["category"])
    env.say("U+%s %s (%s) [%s]" % args)

@command
def ubn(env):
    "Search for a unicode character by name"
    if not env.arg:
        return env.reply(ubn.__doc__)

    flag, arg = api.irc.optflag(arg=env.arg)
    if not arg:
        return env.reply("Need something to search for")

    try: result = api.unicode.by_name(search=arg, categories=flag)
    except api.Error as err:
        return env.reply(str(err))

    def show(result):
        weight, codepoint, data = result
        weight = round(weight, 3)
        args = (codepoint, data["name"], data["display"], data["category"])
        env.say("U+%s %s (%s) [%s]" % args)

    first = result[0]
    weight = first[0]
    show(first)
    if weight > 0.75:
        for r in result[1:]:
            show(r)

@command
def unix_date(env):
    "Show the date using the unix DATE(1) command"
    # @@ database.timezones
    if env.arg:
        date = api.clock.unix_date(zone=env.arg)
    else:
        date = api.clock.unix_date()
    env.say(date)

@command
def unixtime(env):
    "Display the current unix epoch time"
    # import time
    # ought to be in api?
    env.say(str(time.time()))

@command
def utc(env):
    "Display the current date and time in UTC"
    dt = api.clock.datetime_utc()
    env.say(dt)

@command
def val(env):
    "Deprecated: Use i-love-the-w3c instead"
    redirect = "i-love-the-w3c"
    env.reply("Command renamed to %s%s" % (env.prefix, redirect))

@command
def i_love_the_w3c(env): # @@ validate
    "Check a webpage using the W3C Markup Validator."
    if not env.arg:
        return env.reply("Give me a link")

    link = env.arg
    if not link.startswith("http://"):
        link = "http://" + link

    page = api.web.request(
        url="http://validator.w3.org/check",
        query={"uri": link, "output": "xml"}
    )

    result = link + " is "

    if page.status != 200:
        return env.say("Got HTTP response %s" % page.status)

    # @@ api-ise
    if "x-w3c-validator-status" in page.headers:
        status = page.headers["x-w3c-validator-status"]
        result += status
        if status != "Valid":
            if "x-w3c-validator-errors" in page.headers:
                errors = page.headers["x-w3c-validator-errors"]
                n = int(errors.split(" ")[0])
                if n != 1:
                    result += " (%s errors)" % n
                else:
                    result += " (%s error)" % n
    else:
        result += "unvalidatable: no X-W3C-Validator-Status"
    env.say(result)

@command
def version(env):
    "Show duxlot and python version"
    import sys

    duxlot_version = api.general.duxlot_version()
    python_version = sys.version.split(" ", 1)[0]
    env.say("duxlot %s, and python %s" % (duxlot_version, python_version))

@command
def w(env):
    "Look up a word in Wiktionary"
    if not env.arg:
        return env.reply("Wiktionary search: need a word to define")

    article = api.word.wiktionary_article(word=env.arg)
    if not "definitions" in article:
        return env.reply("Couldn't get any definitions for %s" % env.arg)

    result = api.word.wiktionary_format(**article())
    if len(result) < 150:
        result = api.word.wiktionary_format(number=3, **article())
    if len(result) < 150:
        result = api.word.wiktionary_format(number=5, **article())

    if len(result) > 300:
        result = result[:295] + "[...]"
    env.say(result)

@command
def wa(env):
    "Consult Wolfram|Alpha using a web service"
    # 1 + 1 gives an error
    if not env.arg:
        return env.reply(wa.__doc__)

    flag, arg = api.irc.optflag(arg=env.arg)

    # @@ 1 + 1 doesn't work, doesn't recognise the +?
    url = "http://tumbolia.appspot.com/wa/${args}"
    line = api.services.query(url=url, arg=arg)

    if flag is None:
        if line:
            line = api.html.decode_entities(html=line)
            line = line.replace(r"\/", "/")
            line = line.replace(r"\'", "'")
            line = line.replace(";", "; ")
            line = line.replace("  (", " (")
            line = line.replace("~~ ", "~")
            line = line.replace(", , ", ", ")
            env.say(line[:510])
        else:
            env.say("Sorry, no result!")
    elif flag == "":
        env.say(str(list(sorted(response().keys()))))
    elif flag == ":":
        env.say(str(response()))
    else:
        env.say(response()[flag])

@command
def weather(env):
    "Redirect to metar"
    redirect = "metar"
    env.reply("Perhaps you meant %s%s" % (env.prefix, redirect))

@command
def wik(env):
    "Search for an article on Wikipedia"
    if not env.arg:
        return env.reply(wik.__doc__)

    flag, arg = api.irc.optflag(arg=env.arg)

    try: article = api.wikipedia.article(term=arg, language=flag)
    except api.Error as err:
        return env.reply("Couldn't find an article. %s" % err)

    if "sentence" in article:
        message = '"%s" - %s' % (article.sentence, article.url)
        env.say(message)
    else:
        env.reply("Couldn't get that article on Wikipedia")

@command
def yi(env):
    "Calculate whether it is currently yi in tavtime or not"
    yi = api.clock.yi()
    env.reply("Yes, PARTAI!" if yi else "Not yet...")

@command
def zoneinfo_offset(env):
    # @@ no documentation, no args gives weird
    import os.path
    zoneinfo = env.options["zoneinfo"]
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
    if env.text == (env.options["nick"] + "!"):
        env.say(env.nick + "!")

    ### Respond to prefix enquiries ###
    p_commands = {
        env.options["nick"] + ": prefix",
        env.options["nick"] + ": prefix?"
    }
    if env.text in p_commands:
        senders = env.options["prefixes"]
        if env.sender in senders:
            prefix = senders[env.sender]
        else: prefix = env.options["prefix"]

        env.reply("Current prefix for here is \"%s\"" % prefix)

    ### Note channel links ###
    found_links = api.regex_link.findall(env.text)
    if found_links:
        with env.database.context("links") as links:
            links[env.sender] = found_links.pop()

    ### Note nicknames in seen database ###
    if env.sender.startswith("#"):
        private = set(env.options["private"])
        if not (env.sender in private):
            t = time.time()
            with env.database.context("seen") as seen:
                seen[env.nick] = (t, env.sender)

### Other ###

@duxlot.startup
def cache_data(safe):
    # @@ could this be even faster?
    api.clock.cache_timezones_data()
    api.unicode.cache_unicode_data()

web_services_manifest = {}

@duxlot.startup
def create_web_services(safe):
    global web_services_manifest

    safe.database.init("services", {}) # @@ or just load with default
    web_services_manifest = safe.database.cache.services
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
