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
#     if input.admin and (input.sender in options

def zone_from_nick(irc, nick):
    tz = irc.database.cache.timezones.get(nick, None)
    if tz is None:
        return 0, "UTC"
    else:
        import os.path
        zoneinfo = irc.options["zoneinfo"]
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
def about(irc, input):
    "Give information about a named bot command"
    if not input.arg:
        return irc.reply(about.__doc__)

    if input.arg in duxlot.commands:
        function = duxlot.commands[input.arg]
        if hasattr(function, "__doc__") and function.__doc__:
            irc.reply(function.__doc__)
        else:
            irc.reply("That command has no documentation")
    else:
        irc.reply("Couldn't find that command")

# @@ ask, not tell yourself
@command
def ask(irc, input):
    "Ask another user an enquiry"
    if not input.arg:
        return irc.reply(ask.__doc__)

    input.verb = "ask"
    to(irc, input)

@command
def attributes(irc, input):
    "Discover which attributes are available to internal functions"
    # @@ this is broken, input doesn't work
    irc.say("irc: " + ", ".join(irc().keys()))
    irc.say("input: " + ", ".join(b for b in dir(input) if not b.startswith("_")))

@command
def beats(irc, input):
    "Show current time in Swatch internet beats"
    opt = api.clock.beats()
    irc.reply(opt.beats)

# @@ .bing [...]vzmvnncvz
# @@ <duxlot> Python Error. IncompleteRead(27254 bytes read): standard.py:101 bing(...) ?
@command
def bing(irc, input):
    "Search for a phrase on Bing"
    if not input.arg:
        return irc.reply(bing.__doc__)

    try: url = api.search.bing(phrase=input.arg)
    except api.Error:
        return irc.reply("Couldn't find any results")

    if isinstance(url, str):
        irc.reply(url)
    else:
        irc.reply("No results found")

    # @@ could persist this
    # @@ make sends monitorable
    with irc.database.context("links") as links:
        links[input.sender] = url

@command
def botsnack(irc, input):
    "Give the bot a botsnack"
    irc.say(":)")

@command
def bytes(irc, input):
    "Show input argument as python bytes representation"
    # @@ this is giving a space prefix
    command_size = len(input.prefix + "bytes")
    octets = input.message["parameters_octets"][1]
    octets = octets[command_size + 1:]
    irc.reply(repr(octets))

@command
def c(irc, input):
    "Calculate an expression using Google calculator"
    if not input.arg:
        return irc.reply(c.__doc__)

    try: calculation = api.google.calculator(expression=input.arg)
    except api.Error as err:
        return irc.reply(str(err))

    if "response" in calculation:
        irc.say(calculation.response)
    else:
        irc.say("Error")

@command
def calc(irc, input):
    "Calculate an expression using Google calculator"
    c(irc, input)

@command
def chars(irc, input):
    "Unicode characters grep"
    # @@ better doc
    if not input.arg:
        return irc.reply(ucg.__doc__)

    flag, arg = api.irc.optflag(arg=input.arg)
    if not arg:
        return irc.reply("Need something to search for")

    try: result = api.unicode.character_grep(search=arg, categories=flag)
    except api.Error as err:
        return irc.reply(str(err))
    irc.reply(result)

@command
def date(irc, input):
    "Display the current date in UTC"
    offset, abbreviation = zone_from_nick(irc, input.nick)
    message = api.clock.format_datetime(format="%Y-%m-%d", offset=offset)
    irc.say(message)

@command
def decode(irc, input):
    "Decode text containing HTML entities"
    if not input.arg:
        return irc.reply(decode.__doc__)

    text = api.html.decode_entities(html=input.arg)
    irc.say(text)

@command
def duck(irc, input):
    "Search for a phrase on DuckDuckGo"
    if not input.arg:
        return irc.reply(duck.__doc__)

    try: url = api.search.duck(phrase=input.arg)
    except api.Error as err:
        return irc.reply(str(err))

    irc.reply(url)

    with irc.database.context("links") as links:
        links[input.sender] = url

# @@ inamidst.com, without http:// and /
@command
def encoding(irc, input):
    "Determine the encoding of a web page"
    if not input.arg:
        example = "Example: %sencoding http://sbp.so/"
        return irc.reply(example % input.prefix)

    opt = api.web.request(url=input.arg)
    if "encoding" in opt:
        summary = opt.encoding
        if "encoding_source" in opt:
            summary += " (%s)" % opt.encoding_source
        irc.reply(summary)
    elif "error" in opt:
        irc.reply("Error: %s" % opt.error)
    else:
        irc.reply("Couldn't determine the encoding")

@command
def error_test(irc, input):
    "Attempt to divide one by zero"
    1/0

# @@ .ety love - random words?
@command
def ety(irc, input):
    "Display the etymology of a term from Etymonline"
    # @@ .ety love doesn't work
    if not input.arg:
        example = "Example: %setymology frog"
        return irc.reply(example % input.prefix)

    try: opt = api.word.etymology(term=input.arg, limit=input.limit)
    except api.Error as err:
        msg = "Nothing found. Try http://etymonline.com/search.php?term=%s"
        return irc.say (msg % input.arg)

    if "sentence" in opt:
        irc.say('"%s" - %s' % (opt.sentence, opt.url))
    else:
        irc.say("?")

@command
def follow(irc, input):
    "Follow web page redirect and report the destination"
    if not input.arg:
        example = "Example: %sfollow http://sbp.so/p"
        return irc.reply(example % input.prefix)

    opt = api.web.request(
        method="HEAD",
        follow=True,
        url=input.arg
    )

    if "url" in opt:
        irc.reply(opt.url)
    elif "error" in opt:
        irc.reply("Error: %s" % opt.error)
    else:
        irc.reply("Couldn't follow that url")

@command
def g(irc, input):
    "Search for a phrase on Google"
    if not input.arg:
        return irc.reply(g.__doc__)

    try: url = api.google.search_api(phrase=input.arg)
    except api.Error as err:
        return irc.reply(str(err))

    irc.reply(url)

    # @@ could persist this
    with irc.database.context("links") as links:
        links[input.sender] = url

@command
def gc(irc, input):
    "Show the Google search result count of a phrase"
    if not input.arg:
        return irc.reply(gc.__doc__)

    flag, arg = api.irc.optflag(arg=input.arg)
    try: count = api.google.count(phrase=arg, method=flag)
    except api.Error as err:
        return irc.reply(str(err))            

    if flag in {None, "", "*", "all"}:
        # @@ only add the arg if there's been another recent gc
        irc.say("%s - %s" % (count, arg))
    else:
        irc.say("%s: %s" % (arg, count))

@command
def gcs(irc, input):
    "Show the Google search result counts of up to six terms inclusive"
    # broken: §gcs [hello nsh] "what's up?" [this is a demo] of gcs
    if not input.arg:
        return irc.reply(gcs.__doc__)

    flag, arg = api.irc.optflag(arg=input.arg)

    text = "[api] " if (not flag) else ""
    method = "api" if (not flag) else flag

    try: text += api.google.counts_api(terms=arg, method=method)
    except api.Error as err:
        return irc.reply(str(err))            
    irc.say(text)

@command
def gd(irc, input):
    "Get a definition using Google Dictionary"
    # @@ .gd define is a bit spacey
    if not input.arg:
        return irc.reply(gd.__doc__)

    try: definition = api.google.dictionary(term=input.arg)
    except api.Error as err:
        return irc.reply(str(err))

    irc.reply(definition)

@command
def head(irc, input):
    "Get information about a web page using an HTTP HEAD request"
    if not input.arg:
        return irc.reply(head.__doc__)

    # @@ getting ETag won't work
    header = None
    if " " in input.arg:
        a, b = input.arg.split(" ", 1)
        if "." in a:
            url, header = a, b
        else:
            header, url = a, b
    else:
        url = input.arg

    opt = api.web.head_summary(url=url)
    if header:
        if header.lower() in opt.headers:
            return irc.reply(opt.headers[header.lower()])
        else:
            return irc.reply("No header %s in %s" % (header, url))

    irc.reply(opt.summary)

@command
def help(irc, input):
    "Provide details about the bot"
    if input.arg:
        about(irc, input)
    else:
        irc.say("I am duxlot. You are not. WRITTEN IN PYTHON3™")

# @@ filetype, site
@command
def img(irc, input):
    "Search for an image on Google Image Search"
    if not input.arg:
        return irc.reply(img.__doc__)

    try: url = api.google.image(phrase=input.arg)
    except api.Error as err:
        return irc.reply(str(err))

    irc.reply(url)
    import urllib.parse
    arg = urllib.parse.quote(input.arg)
    irc.say("More: http://google.com/images?q=%s" % arg)

@command
def _in(irc, input):
    "Schedule a reminder to be sent after a specified time period"
    if not input.arg:
        return irc.reply(_in.__doc__)

    opt = api.clock.periods_unixtime(text=input.arg)
    if not opt.seconds:
        return irc.reply("Couldn't understand your duration. Use units?")

    e = (opt.unixtime, input.sender, input.nick, opt.remainder)
    irc.schedule(e)

    # @@ needs to use the time zone *at opt.unixtime*, not current!
    offset, abbreviation = zone_from_nick(irc, input.nick)
    phrase = api.clock.duration_phrase(
        tz=abbreviation,
        seconds=opt.seconds,
        unixtime=opt.unixtime,
        offset=offset
    )
    irc.reply("Will remind %s" % phrase)

@command
def ip_time(irc, input):
    "Show the current time guessed for the IP address given"
    # @@ mix with database.timezones
    if not input.arg:
        return irc.reply(ip_time.__doc__)

    try: dt = api.geo.timezone(ip=input.arg)
    except api.Error as err:
        return irc.reply(str(err))
    irc.reply(dt)

@command
def _len(irc, input):
    "Show the length of the input in characters and utf-8 bytes"
    characters = len(input.arg)
    bytes = len(input.arg.encode("utf-8"))
    irc.reply("%s chars, %s bytes (utf-8)" % (characters, bytes))

@command
def leo(irc, input):
    "Search for a term in the LEO German Dictionary"
    # @@ empty results are formatted weirdly
    if not input.arg:
        return irc.reply(leo.__doc__)

    try: opt = api.word.leo(term=input.arg)
    except api.Error as err:
        return irc.reply(str(err))

    if not opt.text.strip():
        return irc.reply("Nothing found at " + opt.url)

    irc.reply(opt.text + " — " + opt.url)

@command
def mangle(irc, input):
    "Put a phrase through the multiple translation mangle"
    if not input.arg:
        return irc.reply(mangle.__doc__)

    # import time
    # @@ this should be in api
    opt = duxlot.Storage()
    opt.source = "en"
    opt.text = input.arg
    for target in ("fr", "de", "es", "it", "ja", "en"): 
        opt.target = target
        opt = api.google.translate(**opt())

        opt.text = opt.translation
        opt.source = opt.target
        time.sleep(1/3)
    irc.reply(opt.translation)

@command
def maximum(irc, input):
    "Discover the maximum number of byte content that can be sent per message"
    if input.limit is None:
        return irc.say("I don't know the text limit at the moment, sorry")
    message = "The maximum length text I can send here is %s bytes"
    irc.say(message % input.limit)

@command
def metar(irc, input):
    "Get a formatted METAR weather summary for an ICAO code"
    if not input.arg:
        example = "Example for London, Heathrow: %smetar EGLL"
        return irc.reply(example % input.prefix)

    summary = api.weather.metar_summary(icao=input.arg)
    irc.reply(summary)

@command
def news(irc, input):
    "Search for a news article on Google News Search"
    if not input.arg:
        return irc.reply(news.__doc__)

    try: url = api.google.news(phrase=input.arg)
    except api.Error as err:
        return irc.reply(str(err))

    irc.reply(url)
    import urllib.parse
    arg = urllib.parse.quote(input.arg)
    irc.say("More: http://google.com/news?q=%s" % arg)

#        send(".noop")
#        receive("This will time out")

# @@ or just "link"
@command
def noted_link(irc, input):
    "Show currently noted link from this channel"
    # @@ not set up with .title yet?
    link = irc.database.cache.links.get(input.sender)
    if link:
        irc.reply(link)
    else:
        irc.reply("No link found for here")

@command
def npl(irc, input):
    "Display the current time from NPL's SNTP server"
    # @@ database.timezones
    opt = api.clock.npl()
    irc.say("%s - %s" % (opt.datetime, opt.server))

@command
def o(irc, input):
    ":O"
    irc.say(":O")

@command
def parse_irc_message(irc, input):
    "Parse a raw IRC message into structured data"
    if not input.arg:
        return irc.reply(parse_irc_message.__doc__)

    octets = input.arg.encode("utf-8")
    o = api.irc.parse_message(octets=octets)
    irc.reply(str(o()))

@command
def parsed_message(irc, input):
    "Show parsed input message"
    irc.reply(repr(input.message))

@command
def ping(irc, input):
    "There is no ping command"
    msg = "%s; nor can this be construed as a response"
    irc.reply(msg % ping.__doc__)

@command
def py(irc, input):
    "Evaluate a python expression using Google App Engine"
    if not input.arg:
        return irc.reply(py.__doc__)

    url = "http://tumbolia.appspot.com/py/${args}"
    line = api.services.query(url=url, arg=input.arg)
    if line:
        irc.say(line[:510])
    else:
        irc.say("Sorry, no result!")

@command
def rhymes(irc, input):
    "Show some perfect rhymes of a word"
    try: text = api.word.rhymes(word=input.arg)
    except api.Error as err:
        irc.reply("Error: " + str(err))
    else:
        irc.reply(text)

@command
def schedule(irc, input):
    "Schedule an event"
    # @@ database.timezones
    if not input.arg:
        return irc.reply(schedule.__doc__)

    t, text = input.arg.split(" ", 1)
    t = float(t)
    irc.schedule((t, input.sender, input.nick, text))
    irc.reply("Scheduled")

@command
def search_trio(irc, input):
    "Search Google, Bing, and DuckDuckGo, and compare the results"
    if not input.arg:
        return irc.reply(search_trio.__doc__)

    result = api.search.trio(phrase=input.arg)
    irc.reply(result)

# @@ test to make sure the right time is given!
@command
def seen(irc, input):
    "Find out whether somebody has been around recently"
    if not input.arg:
        return irc.say(seen.__doc__)

    if input.arg == irc.options["nick"]:
        return irc.reply("I'm right here")

    # irc.database.seen.get.verb.verb.verb
    result = irc.database.cache.seen.get(input.arg)

    if not result:
        irc.say("Haven't seen %s" % input.arg)
    else:
        unixtime, place = result

        offset, abbreviation = zone_from_nick(irc, input.nick)
        dt = api.clock.format_datetime(
            format="%Y-%m-%d %H:%M:%S $TZ",
            offset=offset,
            tz=abbreviation,
            unixtime=unixtime
        )

        irc.say("On %s at %s" % (place, dt))

@command
def snippets(irc, input):
    "Search for snippets using the Google API"
    if not input.arg:
        return irc.reply(snippets.__doc__)

    snippets = api.google.search_api_snippets(phrase=input.arg)
    limit = (input.limit or 256) - len(input.nick + ": ") - 128
    snippets = " / ".join(snippets)[:limit - 3] + "..."
    irc.reply(snippets)

# @@ a check that commands are covered here
@command
def stats(irc, input):
    "Display information about the most used commands"
    usage = irc.database.cache.usage

    usage = sorted(((b, a) for (a, b) in usage.items()), reverse=True)
    usage = list(usage)[:10]
    usage = ["%s (%s)" % (b, a) for (a, b) in usage]
    irc.reply("Top used commands: " + ", ".join(usage))

@command
def suggest(irc, input):
    "Get suggestions using Google Suggest"
    if not input.arg:
        return irc.reply(suggest.__doc__)

    # @@ quote(arg).replace('+', '%2B')
    url = "http://websitedev.de/temp-bin/suggest.pl?q=${args}"
    line = api.services.query(url=url, arg=input.arg)
    if line:
        irc.say(line[:510])
    else:
        irc.say("Sorry, no result!")

@command
def t(irc, input):
    "Display the current date and time"
    # @@ database.timezones
    if not input.arg:
        fmt = "%d %b %Y, %H:%M:%S $TZ"
        offset, abbreviation = zone_from_nick(irc, input.nick)
        dt = api.clock.format_datetime(
            format=fmt,
            offset=offset,
            tz=abbreviation
        )
        irc.say(dt)

    elif input.arg in api.clock.timezones_data:
        dt = api.clock.timezone_datetime(tz=input.arg)
        irc.say(dt) # @@ add the tz name?

    elif api.clock.data.regex_number.match(input.arg):
        offset = float(input.arg) if ("." in input.arg) else int(input.arg)
        dt = api.clock.offset_datetime(offset=offset)
        irc.say(dt)

    elif api.clock.data.regex_zone.match(input.arg):
        unix_date(irc, input)

    else:
        irc.reply("Unknown format: %s" % input.arg)

@command
def tell(irc, input):
    "Tell another user a message"
    if not input.arg:
        return irc.reply(tell.__doc__)

    input.verb = "tell"
    to(irc, input)

@command
def thesaurus(irc, input):
    "Show some synonyms of a word"
    try: text = api.word.thesaurus(word=input.arg)
    except api.Error as err:
        irc.reply("Error: " + str(err))
    else:
        irc.reply(text)

@command
def _time(irc, input):
    "Display the current time in UTC"
    offset, abbreviation = zone_from_nick(irc, input.nick)
    dt = api.clock.format_datetime(format="%H:%M:%S", offset=offset)
    irc.say(dt)

@command
def time_taken(irc, input):
    "Smallest and biggest times taken by the scheduler"
    irc.say("Smallest: %s" % irc.data["smallest_time"])
    irc.say("Biggest: %s" % irc.data["biggest_time"])

# @@ <sbp> ..timer g
# <duxlot[t?]> sbp: http://en.wikipedia.org/wiki/G-force
# <duxlott> sbp: Took 0.52 seconds
@command
def timer(irc, input):
    "Time how long it takes to run another unparametric command"
    if not input.arg:
        return irc.reply(timer.__doc__)
    if " " in input.arg:
        return irc.reply("Command must not be parametric")
        # not only that, but the command must also ignore parameters...
    if input.arg == "timer":
        return irc.reply("That would take too long")

    cmd = duxlot.commands.get(input.arg)
    if not cmd:
        return irc.reply("No such command: \"%s\"" % input.arg[:32]) # @@

    before = time.time()
    cmd(irc, input)
    after = time.time() - before
    irc.reply("Took %s seconds" % round(after, 3))

@command
def timezone(irc, input):
    "Set the user's timezone to an IANA Time Zone Database value"
    tz = irc.database.cache.timezones.get(input.nick, None)

    if not input.arg:        
        if tz:
            return irc.reply("Your timezone is currently set to %s" % tz)
        else:
            return irc.reply("You do not currently have a timezone set")

    if input.arg in {"None", "-", "delete", "remove", "unset"}:
        if tz is None:
            return irc.reply("You do not current have a timezone set")
        with irc.database.context("timezones") as timezones:
            del timezones[input.nick]
        return irc.reply("Your timezone has been un-set")

    if input.arg in {"geo", "guess"}:
        zonename = api.geo.timezone_info(
            address=input.message["prefix"]["host"]
        ).zone
    else:
        zonename = input.arg        

    import os.path
    zoneinfo = irc.options["zoneinfo"]
    zonefile = os.path.join(zoneinfo, zonename)

    try: opt = api.clock.zoneinfo_offset(filename=zonefile)
    except Exception:
        irc.reply("Unrecognised zone. Try using one of the TZ fields here:")
        irc.reply("http://en.wikipedia.org/wiki/List_of_tz_database_time_zones")
    else:
        tz = round(opt.offset, 2)

        with irc.database.context("timezones") as timezones:
            timezones[input.nick] = zonename

        # message = "Set your zone to %s, which is currently %s (%s)"
        message = "Set your TZ to %s; currently %s (UTC %s)"
        hours = round(tz / 3600, 3)
        hours = "+" + str(hours) if (hours >=0) else str(hours)
        hours = hours.rstrip("0").rstrip(".")
        irc.reply(message % (zonename, opt.abbreviation, hours))

# @@ check for double spaces, etc.

@command
def title(irc, input):
    "Get the title of a web page"
    if not input.arg:
        if input.sender in irc.database.cache.links:
            url = irc.database.cache.links[input.sender]
            return irc.reply(api.web.title(url=url, follow=True))
        return irc.reply(title.__doc__)

    url = input.arg

    # @@ make this a general utility function
    if not "/" in url:
        url = url + "/"
    if not "://" in url:
        url = "http://" + url

    irc.reply(api.web.title(url=url, follow=True))

# @@ check nickname sanity
@command
def to(irc, input):
    "Send a message to another user"
    if not input.arg:
        return irc.reply(to.__doc__)

    # import time
    # could be partly moved to api?
    recipient, message = input.arg.split(" ", 1)

    # check syntax of input.nick!
    # "self!" syntax to force a message to self
    if input.nick == recipient:
        return irc.reply("You can tell yourself that")
    if irc.options["nick"] == recipient:
        return irc.reply("Understood")

    if not hasattr(input, "verb"):
        input.verb = None

    # @@ check nick format
    item = (int(time.time()), input.nick, input.verb, recipient, message)
    with irc.database.context("messages") as messages:
        messages.setdefault(recipient, [])
        messages[recipient].append(item)

    irc.reply("Will pass your message to %s" % recipient)

@command
def tock(irc, input):
    "Display the time from the USNO tock server"
    # @@ database.timezones
    opt = api.clock.tock()
    irc.say("\"%s\" - %s" % (opt.date, opt.server))

@command
def tr(irc, input):
    "Translate text from one language to another"
    if not input.arg:
        return irc.reply(tr.__doc__)

    opt = duxlot.Storage()
    opt.source, arg = api.irc.optflag(arg=input.arg)
    opt.target, opt.text = api.irc.optflag(arg=arg)
    opt = api.google.translate(**opt())
    t = opt.translation[:-1] if opt.translation.endswith(".") else opt.translation
    msg = "%s (%s » %s). translate.google.com"
    irc.reply(msg % (opt.translation, opt.source, opt.target))

@command
def tw(irc, input):
    "Show a tweet"
    if not input.arg:
        return irc.reply("Give me a link, a username, or a tweet id")

    def tweet(**kargs):
        try: return api.twitter.tweet(**kargs)
        except api.Error as err:
            return str(err)

    arg = input.arg
    if arg.startswith("@"):
        arg = arg[1:]

    if arg.isdigit():
        tweet = tweet(id=arg)
    elif api.regex_twitter_username.match(arg):
        tweet = tweet(username=arg)
    elif api.regex_twitter_link.match(arg):
        tweet = tweet(url=arg)
    else:
        return irc.reply("Give me a link, a username, or a tweet id")

    irc.say(tweet)

@command
def twitter(irc, input):
    "Show a tweet"
    tw(irc, input)

@command
def tz(irc, input):
    "Convert a time in one time zone to another"
    if not input.arg:
        return irc.reply(tz.__doc__)

    def usage():
        irc.reply("The format is: HH:MM[:SS] ZONE in ZONE")

    if input.arg.count(" ") == 3:
        t, source_zone, verb, target_zone = input.arg.split(" ", 3)
    else:
        return usage()

    kargs = {"time": t, "source": source_zone, "target": target_zone}
    conversion = api.clock.timezone_convert(**kargs)
    if not "target_time" in conversion:
        return usage()

    source = "%s %s" % (conversion.source_time, conversion.source_name)
    target = "%s %s" % (conversion.target_time, conversion.target_name)

    irc.say(source + " = " + target)

@command
def u(irc, input):
    "Perform various unicode search functions"
    if not input.arg:
        return irc.reply(u.__doc__)
    import re

    flag, arg = api.irc.optflag(arg=input.arg)

    regex_digit = re.compile("[0-9]")
    regex_hex = re.compile("(?i)^[0-9A-F]{2,6}$")
    regex_codepoint = re.compile(r"(?i)^(U\+|\\u)[0-9A-F]{2,6}$")
    regex_simple = re.compile(r"^[\x20-\x7E]+$")

    if flag and (not arg):
        ubc(irc, input)
    elif len(arg) == 1:
        ubc(irc, input)
    elif regex_codepoint.match(arg):
        ubcp(irc, input)
    elif regex_digit.search(arg) and regex_hex.match(arg):
        ubcp(irc, input)
    elif not regex_simple.match(arg):
        ubc(irc, input)
    else:
        ubn(irc, input)

@command
def ubc(irc, input):
    "Give data about unicode characters"
    if not input.arg:
        return irc.reply(ubc.__doc__)

    flag, arg = api.irc.optflag(arg=input.arg)
    if flag and (not arg):
        flag, arg = None, input.arg

    kargs = {"characters": arg, "form": flag}
    try: messages = api.unicode.by_character_formatted(**kargs)
    except api.Error as err:
        return irc.reply(str(err))

    irc.say(", ".join(messages))

@command
def ubcp(irc, input):
    "Search for a unicode character by hexadecimal codepoint"
    if not input.arg:
        return irc.reply(ubcp.__doc__)

    flag, arg = api.irc.optflag(arg=input.arg)
    if not arg:
        return irc.reply("Need something to search for")

    for prefix in ("U+", "u+", r"\u"):
        if arg.startswith(prefix):
            arg = arg[2:] # update if adding a different length above
            break

    try: result = api.unicode.by_hexcp(hex=arg, categories=flag)
    except api.Error as err:
        return irc.reply(str(err))

    codepoint, data = result
    args = (codepoint, data["name"], data["display"], data["category"])
    irc.say("U+%s %s (%s) [%s]" % args)

@command
def ubn(irc, input):
    "Search for a unicode character by name"
    if not input.arg:
        return irc.reply(ubn.__doc__)

    flag, arg = api.irc.optflag(arg=input.arg)
    if not arg:
        return irc.reply("Need something to search for")

    try: result = api.unicode.by_name(search=arg, categories=flag)
    except api.Error as err:
        return irc.reply(str(err))

    def show(result):
        weight, codepoint, data = result
        weight = round(weight, 3)
        args = (codepoint, data["name"], data["display"], data["category"])
        irc.say("U+%s %s (%s) [%s]" % args)

    first = result[0]
    weight = first[0]
    show(first)
    if weight > 0.75:
        for r in result[1:]:
            show(r)

@command
def unix_date(irc, input):
    "Show the date using the unix DATE(1) command"
    # @@ database.timezones
    if input.arg:
        date = api.clock.unix_date(zone=input.arg)
    else:
        date = api.clock.unix_date()
    irc.say(date)

@command
def unixtime(irc, input):
    "Display the current unix epoch time"
    # import time
    # ought to be in api?
    irc.say(str(time.time()))

@command
def utc(irc, input):
    "Display the current date and time in UTC"
    dt = api.clock.datetime_utc()
    irc.say(dt)

@command
def val(irc, input):
    "Deprecated: Use i-love-the-w3c instead"
    redirect = "i-love-the-w3c"
    irc.reply("Command renamed to %s%s" % (input.prefix, redirect))

@command
def i_love_the_w3c(irc, input): # @@ validate
    "Check a webpage using the W3C Markup Validator."
    if not input.arg:
        return irc.reply("Give me a link")

    link = input.arg
    if not link.startswith("http://"):
        link = "http://" + link

    page = api.web.request(
        url="http://validator.w3.org/check",
        query={"uri": link, "output": "xml"}
    )

    result = link + " is "

    if page.status != 200:
        return irc.say("Got HTTP response %s" % page.status)

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
    irc.say(result)

@command
def version(irc, input):
    "Show duxlot and python version"
    import sys

    duxlot_version = api.general.duxlot_version()
    python_version = sys.version.split(" ", 1)[0]
    irc.say("duxlot %s, and python %s" % (duxlot_version, python_version))

@command
def w(irc, input):
    "Look up a word in Wiktionary"
    if not input.arg:
        return irc.reply("Wiktionary search: need a word to define")

    article = api.word.wiktionary_article(word=input.arg)
    if not "definitions" in article:
        return irc.reply("Couldn't get any definitions for %s" % input.arg)

    result = api.word.wiktionary_format(**article())
    if len(result) < 150:
        result = api.word.wiktionary_format(number=3, **article())
    if len(result) < 150:
        result = api.word.wiktionary_format(number=5, **article())

    if len(result) > 300:
        result = result[:295] + "[...]"
    irc.say(result)

@command
def wa(irc, input):
    "Consult Wolfram|Alpha using a web service"
    # 1 + 1 gives an error
    if not input.arg:
        return irc.reply(wa.__doc__)

    flag, arg = api.irc.optflag(arg=input.arg)

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
            irc.say(line[:510])
        else:
            irc.say("Sorry, no result!")
    elif flag == "":
        irc.say(str(list(sorted(response().keys()))))
    elif flag == ":":
        irc.say(str(response()))
    else:
        irc.say(response()[flag])

@command
def weather(irc, input):
    "Redirect to metar"
    redirect = "metar"
    irc.reply("Perhaps you meant %s%s" % (input.prefix, redirect))

@command
def wik(irc, input):
    "Search for an article on Wikipedia"
    if not input.arg:
        return irc.reply(wik.__doc__)

    flag, arg = api.irc.optflag(arg=input.arg)

    try: article = api.wikipedia.article(term=arg, language=flag)
    except api.Error as err:
        return irc.reply("Couldn't find an article. %s" % err)

    if "sentence" in article:
        message = '"%s" - %s' % (article.sentence, article.url)
        irc.say(message)
    else:
        irc.reply("Couldn't get that article on Wikipedia")

@command
def yi(irc, input):
    "Calculate whether it is currently yi in tavtime or not"
    yi = api.clock.yi()
    irc.reply("Yes, PARTAI!" if yi else "Not yet...")

@command
def zoneinfo_offset(irc, input):
    # @@ no documentation, no args gives weird
    import os.path
    zoneinfo = irc.options["zoneinfo"]
    zonefile = os.path.join(zoneinfo, input.arg)
    opt = api.clock.zoneinfo_offset(filename=zonefile)
    irc.reply("%s (%s)" % (opt.offset, opt.abbreviation))


### Events ###

# 1st

@event("1st")
def startup(irc, input):
    # @@ limit timezones to a subset of seen
    for name in ("seen", "links", "messages", "timezones"):
        irc.database.init(name, {})

# 433 (Nickname already in use)

@event("433")
def nick_error2(irc, input):
    if ("address" in irc.data):
        nick = input.message["parameters"][1]
        error = "Somebody tried to change my nick to %s," % nick
        error += " but that nick is already in use"
        irc.msg(irc.options["owner"], error)

# PRIVMSG

@event("PRIVMSG")
def privmsg_event(irc, input):
    ### Send any outstanding user messages ###
    if input.nick in irc.database.cache.messages:
        nick_tells = irc.database.cache.messages[input.nick]
        if nick_tells:
            for t, nick, verb, recipient, message in nick_tells:
                datetime = api.clock.datetime_utc(unixtime=t)
                datetime = datetime[:-3] + "Z"
                date = api.clock.date_utc()
                if datetime.startswith(date):
                    datetime = datetime[len(date):].lstrip()

                if verb:
                    args = (recipient, datetime, nick, verb, recipient, message)
                    irc.say("%s: %s <%s> %s %s %s" % args)
                else:
                    args = (recipient, datetime, nick, recipient, message)
                    irc.say("%s: %s <%s> %s: %s" % args)
                # print times properly with respect to recipient currently

        with irc.database.context("messages") as messages:
            del messages[input.nick]

    ### Respond to interjections ###
    if input.text == (irc.options["nick"] + "!"):
        irc.say(input.nick + "!")

    ### Respond to prefix enquiries ###
    p_commands = {
        irc.options["nick"] + ": prefix",
        irc.options["nick"] + ": prefix?"
    }
    if input.text in p_commands:
        senders = irc.options["prefixes"]
        if input.sender in senders:
            prefix = senders[input.sender]
        else: prefix = irc.options["prefix"]

        irc.reply("Current prefix for here is \"%s\"" % prefix)

    ### Note channel links ###
    found_links = api.regex_link.findall(input.text)
    if found_links:
        with irc.database.context("links") as links:
            links[input.sender] = found_links.pop()

    ### Note nicknames in seen database ###
    if input.sender.startswith("#"):
        private = set(irc.options["private"])
        if not (input.sender in private):
            t = time.time()
            with irc.database.context("seen") as seen:
                seen[input.nick] = (t, input.sender)

### Other ###

@duxlot.startup
def cache_data():
    api.clock.cache_timezones_data()
    api.unicode.cache_unicode_data()

@duxlot.startup
def create_web_services():
    manifest = api.services.manifest()
    items = manifest.items()

    for command_name, url in items:
        if command_name in {"py", "wa"}:
            continue

        def create(command_name, url):
            if command_name in duxlot.commands:
                print("Warning: Skipping duplicate: %s" % command_name)
                return

            @duxlot.named(command_name)
            def service(irc, input):
                kargs = {
                    "url": service.url,
                    "arg": input.arg,
                    "nick": input.nick,
                    "sender": input.sender
                }
                line = api.services.query(**kargs)
                if line:
                    irc.say(line[:510])
            service.__doc__ = "Web service: %s" % url
            service.url = url
        create(command_name, url)
