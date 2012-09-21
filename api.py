# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

import datetime
import decimal
import html.entities as entities
import json
import math
import os.path
import pickle
import re
import socket
import struct
import subprocess
import time
import unicodedata
import urllib.parse
import urllib.request

import duxlot

def data(name):
    return os.path.join(duxlot.path, "data", name)

def copy(a, b): # or b, a...
    for key, value in b().items():
        setattr(a, key, value)

class Error(Exception):
    ...

# @@ pre-wrapper for api.text services?

def service(collection):
    def decorate(function):
        def decorated(**kargs):
            # if collection.name == "text":
            #     check args
            args = duxlot.FrozenStorage(kargs)
            # if collection.name == "text":
            #     check result
            return function(args)
        setattr(collection, function.__name__, decorated)
        decorated.__doc__ = function.__doc__
        # @@ .name, canonicalised
        return decorated
    return decorate


### Module: Clock ###

clock = duxlot.Storage()
clock.name = "clock"

@service(clock)
def beats(args):
    out = duxlot.Storage()

    beats = ((time.time() + 3600) % 86400) / 86.4
    out.beats_int = int(math.floor(beats))
    out.beats = "@%03i" % out.beats_int

    return out

@service(clock)
def cache_timezones_data(args):
    with duxlot.filesystem.open(data("timezones.json"), encoding="utf-8") as f:
        clock.timezones_data = json.load(f)

@service(clock)
def date_utc(args):
    # @@ optional suffix?
    if "unixtime" in args:
        dt = datetime.datetime.utcfromtimestamp(args.unixtime)
    else:
        dt = datetime.datetime.utcnow()
    return dt.strftime("%Y-%m-%d")

@service(clock)
def datetime_utc(args):
    # @@ optional suffix?
    if "unixtime" in args:
        dt = datetime.datetime.utcfromtimestamp(args.unixtime)
    else:
        dt = datetime.datetime.utcnow()
    return dt.strftime("%Y-%m-%d %H:%M:%S")

@service(clock)
def duration_phrase(args):
    # tz, seconds, unixtime, offset
    tz = "Z" if (args.tz == "UTC") else " " + args.tz

    if args.seconds >= (3600 * 12):
        format = "on %d %b %Y at %H:%M" + tz
    elif args.seconds >= 60:
        format = "at %H:%M" + tz
    else:
        return "in %s secs" % int(args.seconds)

    return clock.format_datetime(
        unixtime=args.unixtime,
        offset=args.offset,
        format=format
    )

@service(clock)
def format_datetime(args):
    # format - string, can have $D and $TZ too
    # offset - in seconds
    # unixtime - OPT
    # tz - OPT

    if "unixtime" in args:
        dt = datetime.datetime.utcfromtimestamp(args.unixtime)
    else:
        dt = datetime.datetime.utcnow()

    delta = datetime.timedelta(seconds=args.offset)
    adjusted = dt + delta
    formatted = adjusted.strftime(args.format)

    if "$TZ" in args.format:
        if "tz" in args:
            formatted = formatted.replace("$TZ", args.tz)
        else:
            so = "+" + str(args.offset) if (args.offset >= 0) else str(args.offset)
            formatted = formatted.replace("$TZ", so)

    if "$D" in args.format:
        day = adjusted.strftime("%d")
        formatted = formatted.replace("$D", day.lstrip("0"))

    return formatted

@service(clock)
def npl(args):
    out = duxlot.Storage()

    out.server = "ntp1.npl.co.uk"

    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.sendto(b'\x1b' + 47 * b'\0', (out.server, 123))
    data, address = client.recvfrom(1024)

    if data: 
        buf = struct.unpack('B' * 48, data)
        d = decimal.Decimal('0.0')
        for i in range(8):
            d += decimal.Decimal(buf[32 + i]) * \
                decimal.Decimal(str(math.pow(2, (3 - i) * 8)))
        d -= decimal.Decimal(2208988800)
        out.timestamp = str(d)

        a, b = str(d).split('.')
        f = '%Y-%m-%d %H:%M:%S'
        dt = datetime.datetime.utcfromtimestamp(d).strftime(f)
        out.datetime = dt + '.' + b[:6]
    else:
        raise Error("No data was received from %s" % out.server)

    return out

@service(clock)
def offset_datetime(args):
    fmt = args("format", "%d %b %Y, %H:%M:%S $TZ")

    now = datetime.datetime.utcnow()
    delta = datetime.timedelta(seconds=args.offset * 3600)
    dt = (now + delta).strftime(fmt)
    if "tz" in args:
        dt = dt.replace("$TZ", args.tz)
    else:
        so = "+" + str(args.offset) if (args.offset >= 0) else str(args.offset)
        dt = dt.replace("$TZ", so)

    if fmt.startswith("%d"):
        dt = dt.lstrip("0")
    return dt

@service(clock)
def parse_zoneinfo(args):
    # Specification from http://69.36.11.139/tzdb/tzfile-format.html
    # tzfile(5) also gives the information, though less clearly

    with duxlot.filesystem.open(args.filename, "rb") as f:
        def get(struct_format):
            struct_format = "> " + struct_format
            file_bytes = f.read(struct.calcsize(struct_format))
            return struct.unpack(struct_format, file_bytes)
    
        header, version, future_use = get("4s c 15s")
    
        counts = {}
        for name in ("ttisgmt", "ttisstd", "leap", "time", "type", "char"):
            counts[name] = get("l")[0]
    
        transitions = get("%sl" % counts["time"])
        indices = get("%sB" % counts["time"])
    
        ttinfo = []
        for current in range(counts["type"]):
            ttinfo_struct = get("l?B")
            ttinfo.append(ttinfo_struct)
    
        abbreviations = get("%sc" % counts["char"])

    index = 0
    abbreviation_indices = {}
    for abbreviation in b"".join(abbreviations).split(b"\x00"):
        abbreviation_indices[index] = abbreviation.decode("us-ascii")
        index += len(abbreviation) + 1

    for current, ttinfo_struct in enumerate(ttinfo):
        replacement = abbreviation_indices[ttinfo_struct[2]]
        ttinfo[current] = (ttinfo_struct[0], ttinfo_struct[1], replacement)

    offset, dst, abbreviation = ttinfo[0]
    tzinfo = [(None, offset, dst, abbreviation)]
    for transition, index in zip(transitions, indices):
        offset, dst, abbreviation = ttinfo[index]
        tzinfo.append((transition, offset, dst, abbreviation))

    return tzinfo

clock_dict_scales = {
    365.25 * 24 * 3600: ("years", "year", "yrs", "y"),
    29.53059 * 24 * 3600: ("months", "month", "mo"),
    7 * 24 * 3600: ("weeks", "week", "wks", "wk", "w"),
    24 * 3600: ("days", "day", "d"),
    3600: ("hours", "hour", "hrs", "hr", "h"),
    60: ("minutes", "minute", "mins", "min", "m"),
    1: ("seconds", "second", "secs", "sec", "s")
}

clock_dict_scaling = {}
for period, names in clock_dict_scales.items():
    for name in names:
        clock_dict_scaling[name] = period

clock_regex_period = re.compile(r"(?i)([0-9]+(?:\.[0-9]+)?) *([a-z]+)")

@service(clock)
def period_seconds(args):
    out = duxlot.Storage()

    match = clock_regex_period.match(args.period)
    if not match:
        raise Error("Invalid period syntax: %s" % args.period)

    number, unit = match.groups()
    out.number = float(number)
    out.unit = unit.lower()
    if not out.unit in clock_dict_scaling:
        raise Error("Invalid period unit: %s" % out.unit)

    out.scale = clock_dict_scaling[unit]
    out.seconds = out.number * out.scale

    return out

@service(clock)
def periods_seconds(args):
    out = duxlot.Storage()

    out.seconds = 0
    out.periods = 0
    out.durations = []
    out.remainder = args.text

    while True:
        out.remainder = out.remainder.lstrip()
        match = clock_regex_period.match(out.remainder)
        if not match:
            break

        period = match.group(0)
        try: p = clock.period_seconds(period=match.group(0))
        except Error as err:
            break

        out.seconds += p.seconds
        out.periods += 1
        out.durations.append(p.seconds)
        out.remainder = out.remainder[len(period):]

    return out

@service(clock)
def periods_unixtime(args):
    out = duxlot.Storage()

    out.basetime = time.time()
    copy(out, clock.periods_seconds(text=args.text))
    out.unixtime = out.basetime + out.seconds

    return out

@service(clock)
def time_utc(args):
    # @@ optional suffix?
    if "unixtime" in args:
        dt = datetime.datetime.utcfromtimestamp(args.unixtime)
    else:
        dt = datetime.datetime.utcnow()
    return dt.strftime("%H:%M:%S")

@service(clock)
def timezone_convert(args):
    out = duxlot.Storage()

    source = clock.timezone_info(tz=args.source)
    target = clock.timezone_info(tz=args.target)

    if not "name" in source:
        raise Error("Unrecognized timezone: %s" % args.source)
    if not "name" in target:
        raise Error("Unrecognized timezone: %s" % args.target)

    try:
        numbers = args.time.split(":")
        numbers = [int(n.lstrip("0") or "0") for n in numbers]
        if len(numbers) > 3 or len(numbers) < 2:
            raise Error("Parser expected HH:MM[:SS]")

    except Exception as err:
        raise Error("Parser reports: " + str(err))

    tobj = datetime.datetime(2000, 1, 1, *numbers)
    offset = source.offset - target.offset
    result = tobj - datetime.timedelta(seconds=offset * 3600)

    out.source_time = args.time
    out.source_code = args.source
    out.source_name = source.name

    out.target_code = args.target
    out.target_name = target.name
    out.target_time = result.strftime("%H:%M")

    return out

@service(clock)
def timezone_datetime(args):
    tz = clock.timezone_info(tz=args.tz)
    return clock.offset_datetime(**tz())

@service(clock)
def timezone_info(args):
    out = duxlot.Storage()
    timezones = clock.timezones_data

    for tz in list(timezones.keys()):
        timezones[tz.lower()] = timezones[tz]

    if args.tz.lower() in timezones:
        out.name, out.offset = timezones[args.tz.lower()]
    else:
        raise Error("Unknown timezone: %s" % args.tz)
    return out

@service(clock)
def tock(args):
    out = duxlot.Storage()
    page = web.request(url="http://tycho.usno.navy.mil/cgi-bin/timer.pl")
    out.server = "tycho.usno.navy.mil"
    if "date" in page.headers:
        out.date = page.headers["date"]
    else:
        raise Error("Server %s didn't return a Date header" % out.server)
    return out

@service(clock)
def unix_date(args):
    fmt = args("format", "%d %b %Y, %H:%M:%S $TZ")

    if "zone" in args:
        if not clock.data.regex_zone.match(args.zone):
            raise Error("Bad zone format: %s" % args.zone)

        if not os.path.isfile("/usr/share/zoneinfo/" + args.zone):
            raise Error("Zone not supported: %s" % args.zone)

        # the fmt doesn't work
        cmd = ["TZ=%s date" % args.zone] # , "+'%s'" % fmt]
    else: cmd = ["date"]

    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    return p.communicate()[0].decode("utf-8", "replace")

@service(clock)
def version_number(args):
    epoch = args("epoch", 2012)
    now = datetime.datetime.utcnow()
    major = now.year - epoch
    minor = now.month
    patch = now.day
    sub = "%02i%02i" % (now.hour, now.minute)
    return "%s.%s.%s-%s" % (major, minor, patch, sub)

@service(clock)
def yi(args):
    def divide(a, b): 
        return (a / b), (a % b)

    quadraels, remainder = divide(int(time.time()), 1753200)
    raels = quadraels * 4
    extraraels, remainder = divide(remainder, 432000)
    return True if (extraraels == 4) else False

@service(clock)
def zoneinfo_offset(args):
    out = duxlot.Storage()
    now = time.time()
    tzinfo = clock.parse_zoneinfo(filename=args.filename)

    transition, offset, dst, abbreviation = tzinfo[0]
    out.offset = offset
    out.abbreviation = abbreviation

    for transition, offset, dst, abbreviation in tzinfo[1:]:
        if now >= transition:
            out.offset = offset
            out.abbreviation = abbreviation
        else:
            break
    return out

clock.data = duxlot.Storage()
clock.data.regex_number = re.compile(r"^([+-]?[0-9]+(?:\.[0-9]+)?)$")
clock.data.regex_zone = re.compile(r"^[A-Za-z]+(?:/[A-Za-z_]+)*$")

# @@
regex_link = re.compile(r"(http[s]?://[^<> \"\x01]+)[,.]?")


### Module: General ###

general = duxlot.Storage()
general.name = "general"

@service(general)
def duxlot_version(args):
    with duxlot.filesystem.open(data("version"), "r", encoding="ascii") as f:
        version = f.read()
    version = version.rstrip()
    return version

@service(general)
def wolfram_alpha(args):
    page = web.request(
        url="http://www.wolframalpha.com/input/",
        follow=True,
        query={
            "asynchronous": "false",
            "i": args.query
        }
    )

    simples = {
        r"\/": "/",
        r"\'": "'",
        "": "",
        " °": "°",
        "~~": " ~",
        "~~ ": " ~"
    }

    patterns = {
        r"\\n( *\| *)?": ", ",
        r"~~ *\(": "~(",
        r"[ \t]+": " ",
        r"([0-9]{12})[0-9]+": r"\g<1>"
    }

    r_parens = re.compile(r"(\s*)\(\s*(.*?)\s*\)")

    def parentheses(text):
        def replacement(match):
            pre = " " if match.group(1) else ""
            content = match.group(2)
            return pre + "(" + content + ")"
        return r_parens.sub(replacement, text)

    r_superscript = re.compile(r"\^\(?(-?[0-9]+)\)?")

    def superscript(text):
        super = {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
            "5": "⁵", "6": "⁶", "7": "⁷","8": "⁸", "9": "⁹", "-": "⁻"}

        def replacement(match):
            characters = []
            for character in match.group(1):
                characters.append(super.get(character, character))
            return "".join(characters)
        return r_superscript.sub(replacement, text)

    def pretty(text):
        for key, value in simples.items():
            text = text.replace(key, value)

        for key, value in patterns.items():
            text = re.sub(key, value, text)

        text = re.sub(r"[ \t]+\|[ \t]+", ": ", text)
        text = parentheses(text)
        return superscript(text)

    first = ""
    r_stringified = re.compile(r'"stringified":\s"([^"]+)"')
    items = []

    out = duxlot.Storage()
    out.expression = ""
    out.expressions = []

    for i, stringified in enumerate(r_stringified.findall(page.text)):
        # print(">", stringified)
        exp = pretty(stringified)
        if not i:
            out.expression = exp[:]
        else:
            if exp.startswith(out.expression):
                exp = exp[len(out.expression):].lstrip(" =")
            out.expressions.append(exp)
        # print("*", exp)

    sep = "; "

    limit = args().get("limit", 1024)

    if not out.expression:
        out.text = "No results found" # @@ move to wa(...)?
        return out

    out.text = out.expression + " = "
    for exp in out.expressions:
        if len((out.text + exp + sep).encode("utf-8")) > limit:
            break

        out.text += exp + sep
    out.text = out.text.rstrip(sep)

    return out


### Module: Geo ###

geo = duxlot.Storage()
geo.name = "geo"

@service(geo)
def timezone(args):
    out = duxlot.Storage()
    page = web.request(
        url="http://dial-a-page.dpk.org.uk/iptime/",
        query={"ip": args.ip}
    )

    out.json = json.loads(page.text)
    out.zone = out.json["tzinfo"]
    out.tz = out.json["abbreviation"]
    out.offset = out.json["offset_hours"]
    return clock.offset_datetime(**out()) # argh

@service(geo)
def timezone_info(args):
    out = duxlot.Storage()
    page = web.request(
        url="http://dial-a-page.dpk.org.uk/iptime/",
        query={"ip": args.address}
    )

    out.json = json.loads(page.text)
    out.zone = out.json["tzinfo"]
    out.tz = out.json["abbreviation"]
    out.offset = out.json["offset_hours"]
    return out


### Module: Google ###

google = duxlot.Storage()
google.name = "google"

@service(google)
def calculator(args):
    out = duxlot.Storage()

    substitutions = {
        "ϕ": "phi",
        "π": "pi",
        "tau": "(pi*2)",
        "τ": "(pi*2)"
    }

    expression = args.expression
    for a, b in substitutions.items():
        expression = expression.replace(a, b)
    out.expression_substituted = expression

    page = web.request(
        url="http://www.google.com/ig/calculator",
        query={"q": expression}
    )
    out.url = page.url

    def parse(text):
        text = text.strip("{}")
        regex_entry = re.compile(r"(\w+):\s*\"([^\"]*)\",?\s*")
        while text:
            match = regex_entry.match(text)
            if not match:
                break
            yield match.groups()
            text = text[match.end():]

    fields = dict(parse(page.text))
    out.google_left = fields.get("lhs")
    out.google_right = fields.get("rhs")

    if fields.get("error"):
        raise Error("Google indicates that the input may be malformed")

    right = fields.get("rhs", "")
    if right: 
        right = right.encode("iso-8859-1")
        right = right.decode("unicode-escape")

        substitutions = {
            "<sup>": "^(",
            "</sup>": ")",
            "\xA0": "," # nbsp
        }
        for a, b in substitutions.items():
            right = right.replace(a, b)

        # this html.decode_entities is needed: source is JSON, not HTML
        out.response = html.decode_entities(html=right)
    else:
        raise Error("Google indicates a bad 'rhs' field. Malformed input?")

    return out

@service(google)
def count(args):
    arg = args.phrase

    # @@ unused, move to some formatting collection?
    def concise(number):
        if number.endswith(",000,000,000"):
            return number[:-12] + "b"
        if number.endswith(",000,000"):
            return number[:-8] + "m"
        if number.endswith(",000"):
            return number[:-4] + "k"
        return number

    if args.method in {None, "", "*", "all"}:
        a = google.count_api(phrase=arg)
        v = google.count_verbatim(phrase=arg)
        e = google.count_end(phrase=arg)
        s = google.count_site(phrase=arg)

        return ", ".join((
            a + " (api)",
            v + " (vend)",
            e + " (end)",
            s + " (site)"
        ))

    elif args.method in {"a", "api"}:
        return google.count_api(phrase=arg)
    elif args.method in {"v", "vend"}:
        return google.count_verbatim(phrase=arg)
    elif args.method in {"e", "end"}:
        return google.count_end(phrase=arg)
    elif args.method in {"s", "site"}:
        return google.count_site(phrase=arg)

    raise Error("Unknown method: %s" % args.method)

@service(google)
def count_api(args):
    data = google.search_api_json(**args())
    if "responseData" in data:
        if "cursor" in data["responseData"]:
            if "estimatedResultCount" in data["responseData"]["cursor"]:
                    count = data["responseData"]["cursor"]["estimatedResultCount"]
                    return format(int(count), ",")
    return "0"
    # raise Error("Google API JSON didn't contain an estimated result count")

@service(google)
def counts_api(args):
    terms = search.terms(text=args.terms)
    method = args.method
    if len(terms) > 6:
        raise Error("Can only compare up to six terms inclusive")

    results = []
    for i, term in enumerate(terms):
        term = term.strip("[]")
        # bleh, "phrase=term". also use "query" too

        if method in {"a", "api"}:
            count = google.count_api(phrase=term)
        elif method in {"v", "vend"}:
            count = google.count_verbatim(phrase=term)
        elif method in {"e", "end"}:
            count = google.count_end(phrase=term)
        elif method in {"s", "site"}:
            count = google.count_site(phrase=term)
        else:
            raise Error("Unknown method: %s" % method)

        count = count.replace(",", "") # @@

        # except api.Error: count = "0"
        results.append((int(count), term))
        time.sleep(i * 0.2)

    results = list(reversed(sorted(results)))
    return ", ".join("%s (%s)" % (b, format(a, ",")) for (a, b) in results)

@service(google)
def count_site(args):
    regex_google_site_results = re.compile(r"(?i)([0-9,]+) results?")
    regex_google_end_results = re.compile(
        r"(?i)very similar to the ([0-9,]+) already displayed"
    )
    query = {"hl": "en", "q": args.phrase}

    option = args("option")
    if option in {"end", "verbatim"}:
        query["prmd"] = "imvns"
        query["start"] = "950"

        if option == "verbatim":
            query["tbs"] = "li:1"

    page = web.request(
        url="https://www.google.com/search",
        query=query
    )

    if "No results found for" in page.text:
        return "0"
    elif "did not match any documents" in page.text:
        return "0"

    if "start" in query:
        for result in regex_google_end_results.findall(page.text):
            return result
    for result in regex_google_site_results.findall(page.text):
        return result

@service(google)
def count_end(args):
    return google.count_site(option="end", **args())

@service(google)
def count_verbatim(args):
    return google.count_site(option="verbatim", **args())

@service(google)
def dictionary(args):
    ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_0) AppleWebKit/537.1 "
    ua += "(KHTML, like Gecko) Chrome/21.0.1180.82 Safari/537.1"

    page = web.request(
        url="https://www.google.com/search",
        # ?q=%s&tbs=dfn:1" % urllib.parse.quote(args.term),
        headers={"user-agent": ua},
        query={
            "q": args.term,
            "tbs": "dfn:1"
        }
    )

    regex_whitespace = re.compile(r"[ \t\r\n]+")
    regex_definition = re.compile(r'(?ims)<div id="ires">(.*?)</div>')
    search = regex_definition.search(page.text)
    if search:
        content = search.group(1)
        content = content.replace("\u2003/", " (")
        content = content.replace("/\u2003", ") ")
        content = content.replace("</span>", " / ")
        content = html.scrape(html=content)
        content = regex_whitespace.sub(" ", content)
        return content
    raise Error("No definition found")

@service(google)
def image(args):
    page = web.request(
        url="http://ajax.googleapis.com/ajax/services/search/images",
        query={"q": args.phrase, "v": "1.0", "safe": "off"}
    )
    data = json.loads(page.text)
    try: result = data["responseData"]["results"][0]["unescapedUrl"]
    except (KeyError, IndexError):
        raise Error("No image search result found")
    return result

@service(google)
def news(args):
    page = web.request(
        url="http://ajax.googleapis.com/ajax/services/search/news",
        query={"q": args.phrase, "v": "1.0", "safe": "off"}
    )
    data = json.loads(page.text)
    try: result = data["responseData"]["results"][0]["unescapedUrl"]
    except (KeyError, IndexError):
        raise Error("No news search result found")
    return result

@service(google)
def search_api(args):
    data = google.search_api_json(**args())
    if "responseData" in data:
        if "results" in data["responseData"]:
            if data["responseData"]["results"]:
                if "unescapedUrl" in data["responseData"]["results"][0]:
                    return data['responseData']['results'][0]['unescapedUrl']
    raise Error("Google API JSON didn't contain a search result")

@service(google)
def search_api_json(args):
    page = web.request(
        url="http://ajax.googleapis.com/ajax/services/search/web",
        query = {"v": "1.0", "safe": "off", "q": args.phrase}
    )
    return json.loads(page.text)

@service(google)
def search_api_snippets(args):
    regex_whitespace = re.compile(r"[ \t\r\n]+")
    regex_date = re.compile("(?i)(\.{3} )?[A-Z]{3} \d\d?, \d{4}( \.{3})?")
    data = google.search_api_json(**args())
    snippets = []
    for result in data["responseData"]["results"]:
        content = result["content"]
        content = html.scrape(decode=True, html=content)
        content = regex_whitespace.sub(" ", content)
        content = regex_date.sub(" ", content)
        content = regex_whitespace.sub(" ", content)
        snippets.append(content.strip(" ."))
    return snippets

@service(google)
def translate(args):
    # @@ the old -raw mode
    out = duxlot.Storage()
    ua = "Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11"
    out.source = args("source") or "auto"
    out.target = args("target") or "en"

    page = web.request(
        url="http://translate.google.com/translate_a/t",
        headers={"User-Agent": ua},
        query = {
            "client": "t",
            "hl": "en",
            "sl": out.source,
            "tl": out.target,
            "multires": "1",
            "otf": "1",
            "ssel": "0",
            "tsel": "0",
            "uptl": "en",
            "sc": "1",
            "text": args.text
        }
    )

    text = page.text
    while ",," in text:
        text = text.replace(",,", ",null,")
    out.json = json.loads(text)

    if len(out.json) > 2:
        out.source = out.json[2]
    else:
        out.source  = "?"
    translation = "".join(part[0] for part in out.json[0])
    out.translation = translation.replace(" ,", ",")
    return out


### Module: HTML ###

html = duxlot.Storage()
html.name = "html"

@service(html)
def decode_entities(args):
    regex_entity = re.compile(r"&([^;\s]+);")

    def entity(match): 
        name = match.group(1).lower()
        if name.startswith("#x"):
            return chr(int(name[2:], 16))
        elif name.startswith("#"):
            return chr(int(name[1:]))
        elif name in entities.name2codepoint:
            return chr(entities.name2codepoint[name])
        return "[" + name + "]"

    return regex_entity.sub(entity, args.html)

@service(html)
def strip_tags(args):
    regex_tag = re.compile(r"<[^>]+>")
    return regex_tag.sub("", args.html)

@service(html)
def scrape(args):
    text = html.strip_tags(html=args.html)
    if "decode" in args:
        text = html.decode_entities(html=text)
    return text


### Module: IRC ###

irc = duxlot.Storage()
irc.name = "irc"

irc_regex_message = re.compile(br'(?:(:.*?) )?(.*?) (.*)')
irc_regex_address = re.compile(br':?([^!@]*)!?([^@]*)@?(.*)')
irc_regex_parameter = re.compile(br'(?:^|(?<= ))(:.*|[^ ]+)')

@service(irc)
def optflag(args):
    arg = args.arg[:]
    flag = None

    if arg.startswith(":"):
        if " " in arg:
            flag, arg = arg.split(" ", 1)
        else:
            flag, arg = arg, ""
        flag = flag[1:]
    return flag, arg

@service(irc)
def parse_message(args):
    out = duxlot.Storage()
    octets = args.octets.rstrip(b'\r\n')

    message_match = irc_regex_message.match(octets)
    if not message_match:
        raise Error("Malformed")

    prefix, command, parameters = message_match.groups()

    if prefix:
        address_match = irc_regex_address.match(prefix)
        if address_match:
            prefix = address_match.groups()

    parameters = irc_regex_parameter.findall(parameters)
    if parameters and parameters[-1].startswith(b":"):
        parameters[-1] = parameters[-1][1:]

    out.command = command.decode("ascii", "replace")

    out.prefix = {"nick": "", "user": "", "host": ""}
    if prefix:
        out.prefix["nick"] = prefix[0].decode("ascii", "replace")
        out.prefix["user"] = prefix[1].decode("ascii", "replace")
        out.prefix["host"] = prefix[2].decode("ascii", "replace")

    def heuristic_decode(param):
        # @@ could get these from config
        encodings = ("utf-8", "iso-8859-1", "cp1252")
        for encoding in encodings:
            try: return param.decode(encoding)
            except UnicodeDecodeError as err:
                continue
        return param.decode("utf-8", "replace")

    out.parameters_octets = parameters
    out.parameters = [heuristic_decode(p) for p in parameters]
    out.octets = octets
    return out


### Module: Py ###

py = duxlot.Storage()
py.name = "py"

@service(py)
def dict_lower(args):
    lower = {}
    for key, value in args.dict.items():
        lower_key = key.lower()
        if (not ("discard" in args)) and (lower_key in lower):
            raise Error("Duplicate key: %s" % key)
        lower[lower_key] = value
    return lower

@service(py)
def pretty_storage(args):
    text = "%s\n" % args.storage.__class__.__name__
    for key, value in args.storage().items():
        length = 79 - len(key) - len(": ")
        value = str(value)[:length]
        value = value.replace("\t", ".")
        value = value.replace("\r", ".")
        value = value.replace("\n", ".")
        text += key + ": " + value + "\n"
    return text + "\n"


### Module: Search ###

search = duxlot.Storage()
search.name = "search"

@service(search)
def bing(args):
    regex_bing_result = re.compile(r"<h3><a href=\"([^\"]+)\"")

    lang = args("lang", "en-GB")
    page = web.request(
        url="http://www.bing.com/search",
        query={"mkt": lang, "q": args.phrase}
    )

    for url in regex_bing_result.findall(page.text):
        if "r.msn.com/" in url:
            continue
        return url

@service(search)
def duck(args):
    regex_duck_result = re.compile(r'nofollow" class="[^"]+" href="(.*?)">')

    page = web.request(
        url="http://duckduckgo.com/html/",
        query={"q": args.phrase.replace("!", ""), "kl": "uk-en"}
    )

    match = regex_duck_result.search(page.text)
    if match:
        return match.group(1)
    raise Error("No result found for %r" % args.phrase)

@service(search)
def terms(args):
    pattern = r'\+?"[^"\\]*(?:\\.[^"\\]*)*"|\[[^]\\]*(?:\\.[^]\\]*)*\]|\S+'
    regex_search_term = re.compile(pattern)

    terms = []
    text = args.text
    while text:
        text = text.strip()
        match = regex_search_term.match(text)
        if not match:
            raise Error("No search term found, here: %r" % text)

        term = match.group(0)
        terms.append(term)
        text = text[len(term):]
    return terms

@service(search)
def trio(args):
    gu = google.search_api(**args())
    bu = search.bing(**args())
    du = search.duck(**args())

    if (gu == bu) and (bu == du):
        return "[GBD] %s" % gu
    elif (gu == bu):
        return "[GB] %s / [D] %s" % (gu, du)
    elif (bu == du):
        return "[BD] %s / [G] %s" % (bu, gu)
    elif (gu == du):
        return "[GD] %s / [B] %s" % (gu, bu)
    else:
        if len(gu) > 250: gu = "[long-link]"
        if len(bu) > 150: bu = "[long-link]"
        if len(du) > 150: du = "[long-link]"
        return '[G] %s / [B] %s / [D] %s' % (gu, bu, du)


### Module: Services ###

services = duxlot.Storage()
services.name = "services"

@service(services)
def manifest(args):
    page = web.request(url="https://github.com/nslater/oblique/wiki")

    services = {}
    regex_item = re.compile(r"<li>(.*?)</li>")
    for item in regex_item.findall(page.text):
        item = html.scrape(html=item)
        if " " in item:
            command, url = item.split(" ", 1)
            if url.startswith("http://") or url.startswith("https://"):
                services[command] = url

    return services

@service(services)
def query(args):
    url = services.substitute(**args())
    page = web.request(
        url=url,
        limit=512
    )

    octets = page.octets.split(b"\n", 1)[0]
    octets = octets.rstrip(b"\r")
    return octets.decode("utf-8", "replace")

@service(services)
def substitute(args):
    substitutions = {}
    if "arg" in args:
        substitutions["${args}"] = urllib.parse.quote(args.arg, safe="")
    if "nick" in args:
        substitutions["${nick}"] = urllib.parse.quote(args.nick, safe="")
    if "sender" in args:
        substitutions["${sender}"] = urllib.parse.quote(args.sender, safe="")

    url = args.url
    for a, b in substitutions.items():
        url = url.replace(a, b)
    return url


### Module: Text ###

# text
# maximum: chracters, bytes, lines

text = duxlot.Storage()
text.name = "text"

@service(text)
def about(args):
    "Give information about a named bot command"
    if not args.text:
        return text.about.__doc__

    if args.text in text():
        function = getattr(text, args.text)
    elif args.text in duxlot.commands:
        function = duxlot.commands[args.text]
    else:
        return "Couldn't find that command"

    if hasattr(function, "__doc__") and function.__doc__:
        return function.__doc__ or "No documentation!"
    return "That command has no documentation"

@service(text)
def beats(args):
    "Show current time in Swatch internet beats"
    opt = clock.beats()
    return opt.beats

# @@ .bing [...]vzmvnncvz
# @@ <duxlot> Python Error. IncompleteRead(27254 bytes read): standard.py:101 bing(...) ?
@service(text)
def bing(args):
    "Search for a phrase on Bing"
    if not args.text:
        return text.bing.__doc__

    try: url = search.bing(phrase=args.text)
    except Error:
        return "Couldn't find any results"

    if isinstance(url, str):
        return url
    return "No results found"

@service(text)
def bytes(args):
    "Show input argument as python bytes representation"
    # @@ this is giving a space prefix
    return repr(args.text.encode("utf-8"))

@service(text)
def c(args):
    "Calculate an expression using Google calculator"
    if not args.text:
        return text.c.__doc__

    calculation = google.calculator(expression=args.text)
    if "response" in calculation:
        return calculation.response
    return "Error"

text.calc = text.c

@service(text)
def chars(args):
    "Unicode characters grep" # @@ better __doc__ string
    # @@ Silently fails when a disallowed flag is given!
    if not args.text:
        return text.chars.__doc__

    flag, arg = irc.optflag(arg=args.text)
    if not arg:
        return "Need something to search for"

    result = unicode.character_grep(search=arg, categories=flag)
    return result

@service(text)
def date(args):
    "Display the current date in UTC"

    # ZONE FROM NICK
    # @@
    flags = []
    arg = args.text
    for attempt in range(2):
        flag, arg = irc.optflag(arg=arg)
        if flag is None:
            break
        flags.append(flag)

    if len(flags) not in {0, 2}:
        return "Error: Expected zero or two flags"

    if flags:
        offset, abbreviation = tuple(flags)
        offset = int(offset)
    else:
        offset, abbreviation = 0, "UTC"
    # /@@

    return clock.format_datetime(format="%Y-%m-%d", offset=offset)

text.date.argument = "tz"

@service(text)
def decode(args):
    "Decode text containing HTML entities"
    if not args.text:
        return text.decode.__doc__

    return html.decode_entities(html=args.text)

@service(text)
def duck(args):
    "Search for a phrase on DuckDuckGo"
    if not args.text:
        return text.duck.__doc__

    return search.duck(phrase=args.text)

# @@ inamidst.com, without http:// and /
@service(text)
def encoding(args):
    "Determine the encoding of a web page"
    if not args.text:
        return text.encoding.__doc__

    opt = web.request(url=args.text)

    if "encoding" in opt:
        summary = opt.encoding
        if "encoding_source" in opt:
            summary += " (%s)" % opt.encoding_source
        return summary
    elif "error" in opt: # @@
        return "Error: %s" % opt.error

    return "Couldn't determine the encoding"

text.encoding.argument = "link"

# @@ .ety love - random words?
@service(text)
def ety(args):
    "Display the etymology of a term from Etymonline"
    # @@ .ety love doesn't work
    if not args.text:
        return text.ety.__doc__

    limit = args.maximum.get("bytes", 360)

    try: opt = word.etymology(term=args.text, limit=limit)
    except Error as err:
        # @@ URI encoding
        link = "http://etymonline.com/search.php?term=" + args.text
        return "Nothing found. Try " + link

    if "sentence" in opt:
        return "\"%s\" - %s" % (opt.sentence, opt.url)
    return "?"

@service(text)
def follow(args):
    "Follow web page redirect and report the destination"
    if not args.text:
        return text.follow.__doc__

    opt = web.request(
        method="HEAD",
        follow=True,
        url=args.text
    )

    if "url" in opt:
        return opt.url
    elif "error" in opt:
        return "Error: %s" % opt.error
    else:
        return "Couldn't follow that url"

text.follow.argument = "link"

@service(text)
def g(args):
    "Search for a phrase on Google"
    if not args.text:
        return text.g.__doc__

    return google.search_api(phrase=args.text)

@service(text)
def gc(args):
    "Show the Google search result count of a phrase"
    if not args.text:
        return text.gc.__doc__

    flag, arg = irc.optflag(arg=args.text)
    count = google.count(phrase=arg, method=flag)

    # if flag in {None, "", "*", "all"}:
    #     # @@ only add the arg if there's been another recent gc
    #     return "%s - %s" % (count, arg)
    # else:
    return "%s: %s" % (arg, count)

@service(text)
def gcs(args):
    "Show the Google search result counts of up to six terms inclusive"
    # broken: §gcs [hello nsh] "what's up?" [this is a demo] of gcs
    if not args.text:
        return text.gcs.__doc__

    flag, arg = irc.optflag(arg=args.text)

    text = "[api] " if (not flag) else ""
    method = "api" if (not flag) else flag

    text += google.counts_api(terms=arg, method=method)        
    return text

@service(text)
def gd(args):
    "Get a definition using Google Dictionary"
    # @@ .gd define is a bit spacey
    if not args.text:
        return text.gd.__doc__

    return google.dictionary(term=args.text)

# @@ should use recent link
@service(text)
def head(args):
    "Get information about a web page using an HTTP HEAD request"
    if not args.text:
        return text.head.__doc__

    # @@ getting ETag won't work
    header = None
    if " " in args.text:
        a, b = args.text.split(" ", 1)
        if "." in a:
            url, header = a, b
        else:
            header, url = a, b
    else:
        url = args.text

    opt = web.head_summary(url=url)
    if header:
        if header.lower() in opt.headers:
            return opt.headers[header.lower()] or ""
        else:
            return "No header %s in %s" % (header, url)

    return opt.summary or ""

text.head.argument = "link"

@service(text)
def help(args):
    "Provide details about duxlot and commands"
    if args.text:
        return text.about(**args())
    else:
        return "I'm a duxlot. Details: http://inamidst.com/duxlot/"

@service(text)
def i_love_the_w3c(args): # @@ validate
    "Check a webpage using the W3C Markup Validator."
    if not args.text:
        return "Give me a link"

    link = args.text
    if not link.startswith("http://"):
        link = "http://" + link

    page = web.request(
        url="http://validator.w3.org/check",
        query={"uri": link, "output": "xml"}
    )

    result = link + " is "

    if page.status != 200:
        return "Got HTTP response %s" % page.status

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
    return result

text.i_love_the_w3c.argument = "link"

# @@ filetype, site
@service(text)
def img(args):
    "Search for an image on Google Image Search"
    if not args.text:
        return text.img.__doc__

    response = google.image(phrase=args.text)

    if args.maximum.get("lines", 1) > 1:
        response += "\n"
        arg = urllib.parse.quote(args.text)
        response += "More: http://google.com/images?q=%s" % arg

    return response

@service(text)
def ip_time(args):
    "Show the current time guessed for the IP address given"
    # @@ mix with database.timezones
    if not args.text:
        return text.ip_time.__doc__

    return geo.timezone(ip=args.text)

@service(text)
def _len(args):
    "Show the length of the input in characters and utf-8 bytes"
    len_characters = len(args.text)
    len_bytes = len(args.text.encode("utf-8"))
    return "%s chars, %s bytes (utf-8)" % (len_characters, len_bytes)

# text.len = _len

@service(text)
def leo(args):
    "Search for a term in the LEO German Dictionary"
    # @@ empty results are formatted weirdly
    if not args.text:
        return text.leo.__doc__

    opt = word.leo(term=args.text)

    if not opt.text.strip():
        return "Nothing found at " + opt.url

    return opt.text + " — " + opt.url

@service(text)
def mangle(args):
    "Put a phrase through the multiple translation mangle"
    if not args.text:
        return text.mangle.__doc__

    # import time
    # @@ this should be in api
    opt = duxlot.Storage()
    opt.source = "en"
    opt.text = args.text
    for target in ("fr", "de", "es", "it", "ja", "en"): 
        opt.target = target
        opt = google.translate(**opt())

        opt.text = opt.translation
        opt.source = opt.target
        time.sleep(1/3)
    return opt.translation

@service(text)
def metar(args):
    "Get a formatted METAR weather summary for an ICAO code"
    if not args.text:
        return text.metar.__doc__

    return weather.metar_summary(icao=args.text)

@service(text)
def news(args):
    "Search for a news article on Google News Search"
    if not args.text:
        return text.news.__doc__

    response = google.news(phrase=args.text)

    if args.maximum.get("lines", 1) > 1:
        response += "\n"
        arg = urllib.parse.quote(args.text)
        response += "More: http://google.com/news?q=%s" % arg

    return response

@service(text)
def npl(args):
    "Display the current time from NPL's SNTP server"
    # @@ database.timezones
    opt = clock.npl()
    return "%s - %s" % (opt.datetime, opt.server)

@service(text)
def o(args):
    ":O"
    return ":O"

@service(text)
def parse_irc_message(args):
    "Parse a raw IRC message into structured data"
    if not args.text:
        return text.parse_irc_message.__doc__

    octets = args.text.encode("utf-8")
    o = irc.parse_message(octets=octets)
    return str(o())

@service(text)
def ping(args):
    "There is no ping command"
    return text.ping.__doc__ + "; nor can this be construed as a response"

# @@ show all the outputs
@service(text)
def pipe(args):
    "Pipe textual commands together"
    if not args.text:
        return text.pipe.__doc__

    services = text()
    services = services.copy()
    del services["name"]
    del services["pipe"]

    arg = args.text

    flags = []
    while True:
        flag, arg = irc.optflag(arg=arg)
        if flag is None:
            break
        flags.append(flag)

    if not flags:
        msg = "Commands should be given as colon-prefixed flags"
        return msg + " e.g. :news :len Tony Blair"

    limit = args.maximum.get("bytes", 360)

    def link(**kargs):
        for result in regex_link.findall(kargs["text"]):
            return result
        return "No links found"
    if not ("link" in services):
        services["link"] = link

    for flag in flags:
        if not flag in services:
            return "Can't use this command: %s" % flag
 
        arg = services[flag](
            text=arg,
            maximum={
                "bytes": limit,
                "lines": 1
            }
        )

    return arg

@service(text)
def _py(args):
    "Evaluate a python expression using Google App Engine"
    if not args.text:
        return text.py.__doc__

    url = "http://tumbolia.appspot.com/py/${args}"
    line = services.query(url=url, arg=args.text)
    if line:
        return line[:510]
    return "Sorry, no result!"

@service(text)
def rfc(args): # by dpk
    "Get the title and URL of an RFC"
    if not args.text:
        return text.rfc.__doc__
    
    if set(args.text) <= set("0123456789"):
        url = "https://tools.ietf.org/html/rfc" + args.text
    else:
        search = "site:tools.ietf.org/html " + args.text
        url = google.search_api(phrase=search)
    
    return web.title(url=url, follow=True) + ": " + url

@service(text)
def rhymes(args):
    "Show some perfect rhymes of a word"
    if not args.text:
        return text.rhymes.__doc__

    return word.rhymes(word=args.text)

@service(text)
def search_trio(args):
    "Search Google, Bing, and DuckDuckGo, and compare the results"
    if not args.text:
        return text.search_trio.__doc__

    return search.trio(phrase=args.text)

comment = """
@service(text)
def sleep_random(args):
    "Sleep for a random number of seconds"
    import random
    s = random.choice([0, 5, 10, 15, 20])
    time.sleep(s)
    return "%s: slept for %s seconds" % (args.text, s)
"""

@service(text)
def snack(args):
    "Give the api a snack"
    return ":)"

@service(text)
def snippets(args):
    "Search for snippets using the Google API"
    if not args.text:
        return text.snippets.__doc__

    snippets = google.search_api_snippets(phrase=args.text)
    limit = args.maximum.get("bytes", 128)
    limit = min(limit, 128)
    return " / ".join(snippets)[:limit - 3] + "..."

@service(text)
def suggest(args):
    "Get suggestions using Google Suggest"
    if not args.text:
        return text.suggest.__doc__

    # @@ quote(arg).replace('+', '%2B')
    url = "http://websitedev.de/temp-bin/suggest.pl?q=${args}"
    line = services.query(url=url, arg=args.text)
    if line:
        return line[:510]
    return "Sorry, no result!"

@service(text)
def t(args):
    "Display the current date and time"
    # @@ database.timezones

    # ZONE FROM NICK
    # @@
    flags = []
    arg = args.text
    for attempt in range(2):
        flag, arg = irc.optflag(arg=arg)
        if flag is None:
            break
        flags.append(flag)

    if len(flags) not in {0, 2}:
        return "Error: Expected zero or two flags"

    if flags:
        offset, abbreviation = tuple(flags)
        offset = int(offset)
    else:
        offset, abbreviation = 0, "UTC"
    # /@@

    if not arg:
        fmt = "%d %b %Y, %H:%M:%S $TZ"

        return clock.format_datetime(
            format=fmt,
            offset=offset,
            tz=abbreviation
        )

    # @@ upper...
    elif arg.upper() in clock.timezones_data:
        # @@ add the tz name?
        return clock.timezone_datetime(tz=arg.upper())

    elif clock.data.regex_number.match(arg):
        offset = float(arg) if ("." in arg) else int(arg)
        return clock.offset_datetime(offset=offset)

    elif clock.data.regex_zone.match(arg):
        return text.unix_date(text=arg)

    return "Unknown format: %s" % arg

text.t.argument = "tz"

@service(text)
def text_commands(args):
    "Show names of text commands"
    names = [name for name in text() if name != "name"]
    return ", ".join(sorted(names))

@service(text)
def thesaurus(args):
    "Show some synonyms of a word"
    if not args.text:
        return text.thesaurus.__doc__

    return word.thesaurus(word=args.text)

@service(text)
def _time(args):
    "Display the current time in UTC"

    # ZONE FROM NICK
    # @@
    flags = []
    arg = args.text
    for attempt in range(2):
        flag, arg = irc.optflag(arg=arg)
        if flag is None:
            break
        flags.append(flag)

    if len(flags) not in {0, 2}:
        return "Error: Expected zero or two flags"

    if flags:
        offset, abbreviation = tuple(flags)
        offset = int(offset)
    else:
        offset, abbreviation = 0, "UTC"
    # /@@

    return clock.format_datetime(format="%H:%M:%S", offset=offset)

text._time.argument = "tz"

# @@ check for double spaces, etc.
@service(text)
def title(args):
    "Get the title of a web page"
    if not args.text:
        return text.title.__doc__

    url = args.text

    # @@ make this a general utility function
    if not "/" in url:
        url = url + "/"
    if not "://" in url:
        url = "http://" + url

    return web.title(url=url, follow=True)

text.title.argument = "link"

@service(text)
def tock(args):
    "Display the time from the USNO tock server"
    # @@ database.timezones
    opt = clock.tock()
    return "\"%s\" - %s" % (opt.date, opt.server)

# @@ could take a link
@service(text)
def tr(args):
    "Translate text from one language to another"
    if not args.text:
        return text.tr.__doc__

    opt = duxlot.Storage()
    opt.source, arg = irc.optflag(arg=args.text)
    opt.target, opt.text = irc.optflag(arg=arg)
    opt = google.translate(**opt())
    t = opt.translation[:-1] if opt.translation.endswith(".") else opt.translation
    msg = "%s (%s » %s). translate.google.com"
    return msg % (opt.translation, opt.source, opt.target)

@service(text)
def tw(args):
    "Show a tweet"
    if not args.text:
        return "Give me a link, a username, or a tweet id"

    def tweet(**kargs):
        try: return twitter.tweet(**kargs)
        except Error as err:
            return str(err)

    arg = args.text
    if arg.startswith("@"):
        arg = arg[1:]

    if set(arg) <= set("0123456789"):
        tweet = tweet(id=arg)
    elif regex_twitter_username.match(arg):
        tweet = tweet(username=arg)
    elif regex_twitter_link.match(arg):
        tweet = tweet(url=arg)
    else:
        return "Give me a link, a username, or a tweet id"

    return tweet

text.tw.argument = "link"

text.twitter = text.tw
text.twitter.argument = "link"

@service(text)
def tz(args):
    "Convert a time in one time zone to another"
    if not args.text:
        return text.tr.__doc__

    def usage():
        return "The format is: HH:MM[:SS] ZONE in ZONE"

    if args.text.count(" ") == 3:
        t, source_zone, verb, target_zone = args.text.split(" ", 3)
    else:
        return usage()

    kargs = {"time": t, "source": source_zone, "target": target_zone}
    conversion = clock.timezone_convert(**kargs)
    if not "target_time" in conversion:
        return usage()

    source = "%s %s" % (conversion.source_time, conversion.source_name)
    target = "%s %s" % (conversion.target_time, conversion.target_name)

    return source + " = " + target

@service(text)
def u(args):
    "Perform various unicode search functions"
    if not args.text:
        return text.u.__doc__

    import re

    flag, arg = irc.optflag(arg=args.text)

    regex_digit = re.compile("[0-9]")
    # @@ simplify the following two?
    regex_hex = re.compile("(?i)^[0-9A-F]{2,6}$")
    regex_codepoint = re.compile(r"(?i)^(U\+|\\u)[0-9A-F]{2,6}$")
    regex_simple = re.compile(r"^[\x20-\x7E]+$")

    if flag and (not arg):
        return text.ubc(**args())
    elif len(arg) == 1:
        return text.ubc(**args())
    elif regex_codepoint.match(arg):
        return text.ubcp(**args())
    elif regex_digit.search(arg) and regex_hex.match(arg):
        return text.ubcp(**args())
    elif not regex_simple.match(arg):
        return text.ubc(**args())
    else:
        return text.ubn(**args())

@service(text)
def ubc(args):
    "Give data about unicode characters"
    if not args.text:
        return text.ubc.__doc__

    flag, arg = irc.optflag(arg=args.text)
    if flag and (not arg):
        flag, arg = None, args.text

    kargs = {"characters": arg, "form": flag}
    messages = unicode.by_character_formatted(**kargs)
    return ", ".join(messages)

@service(text)
def ubcp(args):
    "Search for a unicode character by hexadecimal codepoint"
    if not args.text:
        return text.ubcp.__doc__

    # @@ Ranges! e.g. 3380-33d8 (requested by dpk)
    flag, arg = irc.optflag(arg=args.text)
    if not arg:
        return "Need something to search for"

    for prefix in ("U+", "u+", r"\u"):
        if arg.startswith(prefix):
            arg = arg[2:] # update if adding a different length above
            break

    codepoint, data = unicode.by_hexcp(hex=arg, categories=flag)
    args = (codepoint, data["name"], data["display"], data["category"])
    return "U+%s %s (%s) [%s]" % args

@service(text)
def ubn(args):
    "Search for a unicode character by name"
    if not args.text:
        return text.ubn.__doc__

    flag, arg = irc.optflag(arg=args.text)
    if not arg:
        return "Need something to search for"

    result = unicode.by_name(search=arg, categories=flag)

    def show(result):
        weight, codepoint, data = result
        weight = round(weight, 3)
        args = (codepoint, data["name"], data["display"], data["category"])
        return "U+%s %s (%s) [%s]" % args

    first = result[0]
    weight = first[0]

    response = []

    response.append(show(first))
    if args.maximum.get("lines", 1) < 2:
        return response[0]

    if weight > 0.75:
        for r in result[1:]:
            response.append(show(r))
    return "\n".join(response)

@service(text)
def unix_date(args):
    "Show the date using the unix DATE(1) command"
    # @@ database.timezones
    if args.text:
        return clock.unix_date(zone=args.text)
    else:
        return clock.unix_date()

@service(text)
def unixtime(args):
    "Display the current unix epoch time"
    return str(time.time())

@service(text)
def utc(args):
    "Display the current date and time in UTC"
    return clock.datetime_utc()

@service(text)
def version(args):
    "Show duxlot and python version"
    import sys

    duxlot_version = general.duxlot_version()
    python_version = sys.version.split(" ", 1)[0]
    return "duxlot %s, and python %s" % (duxlot_version, python_version)

@service(text)
def w(args):
    "Look up a word in Wiktionary"
    if not args.text:
        return "Wiktionary search: need a word to define"

    article = word.wiktionary_article(word=args.text)
    if not "definitions" in article:
        return "Couldn't get any definitions for %s" % args.text

    result = word.wiktionary_format(**article())
    if len(result) < 150:
        result = word.wiktionary_format(number=3, **article())
    if len(result) < 150:
        result = word.wiktionary_format(number=5, **article())

    if len(result) > 300:
        result = result[:295] + "[...]"
    return result

@service(text)
def wa(args):
    "Consult Wolfram|Alpha"
    limit = args.maximum.get("bytes") or \
        args.maximum.get("characters") or 256
    o = general.wolfram_alpha(query=args.text, limit=limit)
    return o.text

comment = """
# @@ can this take a link?
@service(text)
def wa_service(args):
    "Consult Wolfram|Alpha using a web service"
    # 1 + 1 gives an error
    if not args.text:
        return text.wa.__doc__

    flag, arg = irc.optflag(arg=args.text)

    # @@ 1 + 1 doesn't work, doesn't recognise the +?
    url = "http://tumbolia.appspot.com/wa/${args}"
    line = services.query(url=url, arg=arg)

    if flag is None:
        if line:
            line = html.decode_entities(html=line)
            line = line.replace(r"\/", "/")
            line = line.replace(r"\'", "'")
            line = line.replace(";", "; ")
            line = line.replace("  (", " (")
            line = line.replace("~~ ", "~")
            line = line.replace(", , ", ", ")
            return line[:510]
        else:
            return "Sorry, no result!"
    elif flag == "":
        return str(list(sorted(response().keys())))
    elif flag == ":":
        return str(response())
    else:
        return response()[flag]
"""

@service(text)
def wik(args):
    "Search for an article on Wikipedia"
    if not args.text:
        return text.wik.__doc__

    flag, arg = irc.optflag(arg=args.text)

    try: article = wikipedia.article(term=arg, language=flag)
    except Error as err:
        return "Couldn't find an article. %s" % err

    if "sentence" in article:
        return '"%s" - %s' % (article.sentence, article.url)
    else:
        return "Couldn't get that article on Wikipedia"

@service(text)
def yi(args):
    "Calculate whether it is currently yi in tavtime or not"
    yi = clock.yi()
    return "Yes, PARTAI!" if yi else "Not yet..."


### Module: Twitter ###

twitter = duxlot.Storage()
twitter.name = "twitter"

regex_twitter_username = re.compile(r"^[a-zA-Z0-9_]{1,15}$")
regex_twitter_link = re.compile(r"^https?://twitter.com/\S+$")
regex_twitter_p = re.compile(r"(?ims)(<p class=\"js-tweet-text.*?</p>)")
regex_twitter_tag = re.compile(r"(?ims)<[^>]+>")
regex_twitter_anchor = re.compile(r"(?ims)(<a.*?</a>)")
regex_twitter_exp = re.compile(r"(?ims)data-expanded-url=[\"'](.*?)[\"']")
regex_twitter_whiteline = re.compile(r"(?ims)[ \t]+[\r\n]+")
regex_twitter_breaks = re.compile(r"(?ims)[\r\n]+")
regex_twitter_b = re.compile(r"(?ims)<b>(.+?)</b>")
regex_twitter_canonical = \
    re.compile(r'rel="canonical" href="https?://twitter.com/([^/\">]+)')

@service(twitter)
def page(args):
    out = duxlot.Storage()
    page = web.request(follow=True, **args())
    text = page.text

    if not "username" in args:
        out.username = "?"
        for username in regex_twitter_canonical.findall(text):
            out.username = username
            break

    shim = '<div class="content clearfix">'
    if shim in text:
        text = text.split(shim, 1).pop()

    def expand(tweet):
        def replacement(match):
            anchor = match.group(1)
            for link in regex_twitter_exp.findall(anchor):
                return link
            return regex_twitter_tag.sub("", anchor)
        return regex_twitter_anchor.sub(replacement, tweet)

    for paragraph in regex_twitter_p.findall(text):
        preamble = text.split('p class="js-tweet-text', 1)[0][-512:]
        for retweeted in regex_twitter_b.findall(preamble):
            if retweeted != out.username:
                out.retweeted = retweeted

        paragraph = expand(paragraph)
        paragraph = regex_twitter_tag.sub("", paragraph)
        paragraph = paragraph.strip()
        paragraph = regex_twitter_whiteline.sub(" ", paragraph)
        out.tweet = regex_twitter_breaks.sub(" ", paragraph)
        break

    if not "tweet" in out:
        raise Error("Couldn't get a tweet from %s" % page.url)
    return out

@service(twitter)
def format_tweet(args):
    if "retweeted" in args:
        return "%s (@%s, RT @%s)" % (args.tweet, args.username, args.retweeted)
    return "%s (@%s)" % (args.tweet, args.username)

@service(twitter)
def tweet(args):
    if "username" in args:
        url = "https://twitter.com/" + args.username + "?" + str(time.time())
        opt = twitter.page(url=url)
        return twitter.format_tweet(**opt())

    elif "id" in args:
        url = "https://twitter.com/twitter/status/" + args.id
        opt = twitter.page(url=url)
        return twitter.format_tweet(**opt())

    elif "url" in args:
        opt = twitter.page(url=args.url)
        return twitter.format_tweet(**opt())

    raise Error("Needed username, id, or url")


### Module: Unicode ###

unicode = duxlot.Storage()
unicode.name = "unicode"

# cp_text: (cp_int, current, ancient, name, category, character, display)
# cp: num, name, current, ancient, cat, category, char, display

@service(unicode)
def by_character(args):
    characters = args.characters
    if args("form"):
        try: characters = unicodedata.normalize(args.form, characters)
        except ValueError:
            raise Error("Normalisation using form %s failed" % args.form.upper())

    data = []
    for character in characters:
        cp = ord(character)
        if 0 <= cp <= 0xFFFF:
            hexcp = "%04X" % cp
        elif 0x10000 <= cp <= 0x10FFFF:
            hexcp = "%06X" % cp
        data.append(unicode.unicode_data[hexcp])
    return data

@service(unicode)
def by_character_formatted(args):
    characters = args.characters
    form = args("form")
    limit = args("limit") or 3

    data_list = unicode.by_character(characters=characters, form=form)

    messages = []
    for data in data_list[:limit]:
        args = (data["hexcp"], data["name"], data["display"], data["category"])
        messages.append("U+%s %s (%s) [%s]" % args)
    if len(data_list) > limit:
        messages.append("...")

    return messages

@service(unicode)
def by_hexcp(args):
    if args("categories"):
        categories = set(args.categories.upper())
    else:
        categories = None

    regex_number = re.compile("(?i)0*" + args.hex)
    for cp, data in sorted(unicode.unicode_data.items()):
        if categories:
            if data["category"] not in categories:
                continue

        if regex_number.match(cp):
            return cp, data

    raise Error("No unicode character found")

comment = """
@service(unicode)
def by_hexcps(args):
    if args("categories"):
        categories = set(args.categories.upper())
    else:
        categories = None

    a, b = args.range.split("-")
    a = int(a.lstrip("0") or 0, 16)
    b = int(b.lstrip("0") or 0, 16)

    results = []
    for cp, data in sorted(unicode.unicode_data.items()):
        if categories:
            if data["category"] not in categories:
                continue

        if a <= data["codepoint"] <= b:
            results.append((cp, data))

    raise Error("No unicode character found")
"""

@service(unicode)
def by_name(args):
    if args("categories"):
        categories = set(args.categories.upper())
    else:
        categories = None

    regex_metachar = re.compile("[%s]" % re.escape(r"$()*+.?[\]^{|}"))
    if regex_metachar.search(args.search):
        pattern = args.search
    else:
        pattern = ".*".join(r"\b" + word for word in args.search.split(" "))
    regex_pattern = re.compile("(?i)" + pattern)

    results = []
    for cp, data in unicode.unicode_data.items():
        if categories:
            if data["category"] not in categories:
                continue

        match = regex_pattern.search(data["current"])
        if match:
            version = .4
        else:
            match = regex_pattern.search(data["ancient"])
            if match:
                version = .6
            else:
                continue

        length = len(data["name"]) / 60
        length = length if (length <= .5) else .5

        position = data["codepoint"] / 0xFFFF
        position = position if (position <= 1) else 1

        weight = version + length + position
        # DerivedAge might make a good weight

        results.append((weight, cp, data))

    if not results:
        raise Error("No characters found")

    results = sorted(results)
    return results[:2]

@service(unicode)
def cache_unicode_data(args):
    unicode.unicode_data = unicode.load_unicode_data()

@service(unicode)
def character_data(args):
    out = duxlot.Storage()

    out.hexcp = args.a
    out.unicode_category = args.c
    out.codepoint = int(args.a, 16)

    # Skip surrogates
    if args.a in {"D800", "DB7F", "DB80", "DBFF", "DC00", "DFFF"}:
        out.character = None
    else:
        out.character = chr(out.codepoint)
    out.category = {
        "C": "O",
        "M": "C",
        "Z": "W"
    }.get(args.c[0], args.c[0])


    if args.c.startswith("M"): # @@ just Mn?
        out.display = "\u25CC" + out.character
    elif args.c.startswith("C") and not args.c.endswith("o"):
        # Co is Private_Use, allow those
        if 0 <= out.codepoint <= 0x1F:
            out.display = chr(out.codepoint + 0x2400)
        else:
            out.display = "<%s>" % args.c
    else:
        out.display = out.character

    if args.b != "<control>":
        out.name = args.b
    else:
        out.name = args.k or args.b
    out.current = args.b
    out.ancient = args.k
    return out

@service(unicode)
def character_grep(args):
    # @@ limits, count of extra characters
    if args("categories"):
        categories = set(args.categories.upper())
    else:
        categories = None

    pattern_cp = r"(?:U\+|\\u)?([0-9A-F]{2,6})"
    regex_codepoint = re.compile(r"(?i)^%s$" % pattern_cp)
    regex_codepoints = re.compile(r"(?i)^%s-%s$" % (pattern_cp, pattern_cp))

    cp = regex_codepoint.match(args.search)
    cps = regex_codepoints.match(args.search)

    results = []
    length = 0

    if (cp is not None) or (cps is not None):
        if cp is not None:
            a, b = cp.group(1), cp.group(1)
        else:
            a, b = cps.group(1), cps.group(2)

        a = int(a.lstrip("0") or 0, 16)
        b = int(b.lstrip("0") or 0, 16)

        for cp, data in sorted(unicode.unicode_data.items()):
            if categories:
                if data["category"] not in categories:
                    continue

            if not (a <= data["codepoint"] <= b):
                continue

            results.append(data["display"])
            length += len(data["display"].encode("utf-8")) + 1
            if length >= 384:
                break
    else:
        # @@ this is duplicated
        regex_metachar = re.compile("[%s]" % re.escape(r"$()*+.?[\]^{|}"))
        if regex_metachar.search(args.search):
            pattern = args.search
        else:
            pattern = ".*".join(r"\b" + word for word in args.search.split(" "))
        regex_pattern = re.compile("(?i)" + pattern)
    
        for cp, data in sorted(unicode.unicode_data.items()):
            if categories:
                if data["category"] not in categories:
                    continue
    
            if not regex_pattern.search(data["name"]):
                continue
    
            results.append(data["display"])
            length += len(data["display"].encode("utf-8")) + 1
            if length >= 384:
                break

    if not results:
        raise Error("No characters found")

    return " ".join(results)

@service(unicode)
def codepoint_category(args):
    return unicode.unicode_data[args.codepoint]["category"]

@service(unicode)
def codepoint_display(args):
    out = duxlot.Storage()

    category = unicode.codepoint_category(**args())
    out.number = int(args.codepoint, 16)
    out.character = chr(out.number)

    if category.startswith("M"): # @@ just Mn?
        out.text = "\u25CC" + out.character
    elif category.startswith("C") and not category.endswith("o"):
        # Co is Private_Use, allow those
        if 0 <= out.number <= 0x1F:
            out.symbol = chr(out.number + 0x2400)
            out.text = chr(out.number + 0x2400)
        else:
            out.text = "<control>"
    else:
        out.text = out.character
    return out

@service(unicode)
def hundred_opens(args):
    out = duxlot.Storage()
    before = time.time()
    for attempt in range(100):
        unicode.load_unicode_data()
    out.duration = time.time() - before
    return out

@service(unicode)
def load_unicode_data(args):
    with duxlot.filesystem.open(data("unicodedata.pickle"), "rb") as f:
        return pickle.load(f)

@service(unicode)
def supercombiner(args):
    chars = ["u"]
    for codepoint in range(0, 3000):
        char = chr(codepoint)
        if unicodedata.category(char) == 'Mn':
            chars.append(char)
        if len(chars) > 100:
            break
    return "".join(chars)

@service(unicode)
def update_unicode_data(args):
    unicode_data = {}
    url = "http://unicode.org/Public/UNIDATA/UnicodeData.txt"
    page = web.request(url=url)
    for line in page.text.splitlines():
        a, b, c, d, e, f, g, h, i, j, k, l, m, n, o = line.split(";")
        data = unicode.character_data(a=a, b=b, c=c, k=k)
        unicode_data[a] = data()
    with duxlot.filesystem.open(data("unicodedata.pickle"), "wb") as f:
        pickle.dump(unicode_data, f)


### Module: Weather ###

weather = duxlot.Storage()
weather.name = "weather"

@service(weather)
def metar_summary(args):
    url = "http://weather.noaa.gov/pub/data/observations/metar/stations/%s.TXT"
    page = web.request(
        url=url % args.icao
    )

    metar = page.text.splitlines().pop()
    metar = metar.split(" ")

    if len(metar[0]) == 4: 
        metar = metar[1:]

    if metar[0].endswith("Z"): 
        time = metar[0]
        metar = metar[1:]
    else: time = None

    if metar[0] == "AUTO": 
        metar = metar[1:]
    if metar[0] == "VC": 
        raise Error(args.icao + ": no data provided")

    if metar[0].endswith("KT"): 
        wind = metar[0]
        metar = metar[1:]
    else: wind = None

    if ("V" in metar[0]) and (metar[0] != "CAVOK"): 
        vari = metar[0]
        metar = metar[1:]
    else: vari = None

    if ((len(metar[0]) == 4) or 
         metar[0].endswith("SM")): 
        visibility = metar[0]
        metar = metar[1:]
    else: visibility = None

    while metar[0].startswith("R") and (metar[0].endswith("L") 
                                                or "L/" in metar[0]): 
        metar = metar[1:]

    if len(metar[0]) == 6 and (metar[0].endswith("N") or 
                                        metar[0].endswith("E") or 
                                        metar[0].endswith("S") or 
                                        metar[0].endswith("W")): 
        metar = metar[1:] # 7000SE?

    cond = []
    while (((len(metar[0]) < 5) or 
             metar[0].startswith("+") or 
             metar[0].startswith("-")) and (not (metar[0].startswith("VV") or
             metar[0].startswith("SKC") or metar[0].startswith("CLR") or 
             metar[0].startswith("FEW") or metar[0].startswith("SCT") or 
             metar[0].startswith("BKN") or metar[0].startswith("OVC")))): 
        cond.append(metar[0])
        metar = metar[1:]

    while "/P" in metar[0]: 
        metar = metar[1:]

    if not metar: 
        raise Error(opt.icao + ": no data provided")

    cover = []
    while (metar[0].startswith("VV") or metar[0].startswith("SKC") or
             metar[0].startswith("CLR") or metar[0].startswith("FEW") or
             metar[0].startswith("SCT") or metar[0].startswith("BKN") or
             metar[0].startswith("OVC")): 
        cover.append(metar[0])
        metar = metar[1:]
        if not metar: 
            raise Error(opt.icao + ": no data provided")

    if metar[0] == "CAVOK": 
        cover.append("CLR")
        metar = metar[1:]

    if metar[0] == "PRFG": 
        cover.append("CLR") # @@?
        metar = metar[1:]

    if metar[0] == "NSC": 
        cover.append("CLR")
        metar = metar[1:]

    if ("/" in metar[0]) or (len(metar[0]) == 5 and metar[0][2] == "."): 
        temp = metar[0]
        metar = metar[1:]
    else: temp = None

    if metar[0].startswith("QFE"): 
        metar = metar[1:]

    if metar[0].startswith("Q") or metar[0].startswith("A"): 
        pressure = metar[0]
        metar = metar[1:]
    else: pressure = None

    if time: 
        hour = time[2:4]
        minute = time[4:6]
        time = "%s:%s" % (hour, minute) # local(icao_code, hour, minute)
    else: time = "(time unknown)"

    if wind: 
        speed = int(wind[3:5])
        if speed < 1: 
            description = "Calm"
        elif speed < 4: 
            description = "Light air"
        elif speed < 7: 
            description = "Light breeze"
        elif speed < 11: 
            description = "Gentle breeze"
        elif speed < 16: 
            description = "Moderate breeze"
        elif speed < 22: 
            description = "Fresh breeze"
        elif speed < 28: 
            description = "Strong breeze"
        elif speed < 34: 
            description = "Near gale"
        elif speed < 41: 
            description = "Gale"
        elif speed < 48: 
            description = "Strong gale"
        elif speed < 56: 
            description = "Storm"
        elif speed < 64: 
            description = "Violent storm"
        else: description = "Hurricane"

        degrees = wind[0:3]
        if degrees == "VRB": 
            degrees = "\u21BB"
        else:
            deg = float(degrees)
            if (deg <= 22.5) or (deg > 337.5): 
                degrees = "\u2191"
            elif (deg > 22.5) and (deg <= 67.5): 
                degrees = "\u2197"
            elif (deg > 67.5) and (deg <= 112.5): 
                degrees = "\u2192"
            elif (deg > 112.5) and (deg <= 157.5): 
                degrees = "\u2198"
            elif (deg > 157.5) and (deg <= 202.5): 
                degrees = "\u2193"
            elif (deg > 202.5) and (deg <= 247.5): 
                degrees = "\u2199"
            elif (deg > 247.5) and (deg <= 292.5): 
                degrees = "\u2190"
            elif (deg > 292.5) and (deg <= 337.5): 
                degrees = "\u2196"

        if not args.icao.startswith("EN") and not args.icao.startswith("ED"): 
            wind = "%s %skt (%s)" % (description, speed, degrees)
        elif args.icao.startswith("ED"): 
            kmh = int(round(speed * 1.852, 0))
            wind = "%s %skm/h (%skt) (%s)" % (description, kmh, speed, degrees)
        elif args.icao.startswith("EN"): 
            ms = int(round(speed * 0.514444444, 0))
            wind = "%s %sm/s (%skt) (%s)" % (description, ms, speed, degrees)
    else: wind = "(wind unknown)"

    if visibility: 
        visibility = visibility + "m"
    else: visibility = "(visibility unknown)"

    if cover: 
        level = None
        for c in cover: 
            if c.startswith("OVC") or c.startswith("VV"): 
                if (level is None) or (level < 8): 
                    level = 8
            elif c.startswith("BKN"): 
                if (level is None) or (level < 5): 
                    level = 5
            elif c.startswith("SCT"): 
                if (level is None) or (level < 3): 
                    level = 3
            elif c.startswith("FEW"): 
                if (level is None) or (level < 1): 
                    level = 1
            elif c.startswith("SKC") or c.startswith("CLR"): 
                if level is None: 
                    level = 0

        if level == 8: 
            cover = "Overcast \u2601"
        elif level == 5: 
            cover = "Cloudy"
        elif level == 3: 
            cover = "Scattered"
        elif (level == 1) or (level == 0): 
            cover = "Clear \u263C"
        else: cover = "Cover Unknown"
    else: cover = "Cover Unknown"

    if temp: 
        if "/" in temp: 
            temp = temp.split("/")[0]
        else: temp = temp.split(".")[0]
        if temp.startswith("M"): 
            temp = "-" + temp[1:]
        try: temp = int(temp)
        except ValueError: temp = "?"
    else: temp = "?"

    if pressure: 
        if pressure.startswith("Q"): 
            pressure = pressure.lstrip("Q")
            if pressure != "NIL": 
                pressure = str(int(pressure)) + "mb"
            else: pressure = "?mb"
        elif pressure.startswith("A"): 
            pressure = pressure.lstrip("A")
            if pressure != "NIL": 
                inches = pressure[:2] + "." + pressure[2:]
                mb = int(float(inches) * 33.7685)
                pressure = "%sin (%smb)" % (inches, mb)
            else: pressure = "?mb"

            if isinstance(temp, int): 
                f = round((temp * 1.8) + 32, 2)
                temp = "%s\u2109 (%s\u2103)" % (f, temp)
    else: pressure = "?mb"
    if isinstance(temp, int): 
        temp = "%s\u2103" % temp

    if cond: 
        conds = cond
        cond = ""

        intensities = {
            "-": "Light", 
            "+": "Heavy"
        }

        descriptors = {
            "MI": "Shallow", 
            "PR": "Partial", 
            "BC": "Patches", 
            "DR": "Drifting", 
            "BL": "Blowing", 
            "SH": "Showers of", 
            "TS": "Thundery", 
            "FZ": "Freezing", 
            "VC": "In the vicinity:"
        }

        phenomena = {
            "DZ": "Drizzle", 
            "RA": "Rain", 
            "SN": "Snow", 
            "SG": "Snow Grains", 
            "IC": "Ice Crystals", 
            "PL": "Ice Pellets", 
            "GR": "Hail", 
            "GS": "Small Hail", 
            "UP": "Unknown Precipitation", 
            "BR": "Mist", 
            "FG": "Fog", 
            "F": "Smoke", 
            "VA": "Volcanic Ash", 
            "D": "Dust", 
            "SA": "Sand", 
            "HZ": "Haze", 
            "PY": "Spray", 
            "PO": "Whirls", 
            "SQ": "Squalls", 
            "FC": "Tornado", 
            "SS": "Sandstorm", 
            "DS": "Duststorm", 
            # ? Cf. http://swhack.com/logs/2007-10-05#T07-58-56
            "TS": "Thunderstorm", 
            "SH": "Showers"
        }

        for c in conds: 
            if c.endswith("//"): 
                if cond: cond += ", "
                cond += "Some Precipitation"
            elif len(c) == 5: 
                intensity = intensities[c[0]]
                descriptor = descriptors[c[1:3]]
                phenomenon = phenomena.get(c[3:], c[3:])
                if cond: cond += ", "
                cond += intensity + " " + descriptor + " " + phenomenon
            elif len(c) == 4: 
                descriptor = descriptors.get(c[:2], c[:2])
                phenomenon = phenomena.get(c[2:], c[2:])
                if cond: cond += ", "
                cond += descriptor + " " + phenomenon
            elif len(c) == 3: 
                intensity = intensities.get(c[0], c[0])
                phenomenon = phenomena.get(c[1:], c[1:])
                if cond: cond += ", "
                cond += intensity + " " + phenomenon
            elif len(c) == 2: 
                phenomenon = phenomena.get(c, c)
                if cond: cond += ", "
                cond += phenomenon

    if not cond: 
        fmt = "%s, %s, %s, %s - %s %s"
        args = (cover, temp, pressure, wind, str(args.icao), time)
    else: 
        fmt = "%s, %s, %s, %s, %s - %s, %s"
        args = (cover, temp, pressure, cond, wind, str(args.icao), time)
    return fmt % args


### Module: Web ###

web = duxlot.Storage()
web.name = "web"

@service(web)
def construct_url(args):
    out = duxlot.Storage()
    if "url" in args:
        safe = "".join(chr(i) for i in range(0x01, 0x80))
        out.base = urllib.parse.quote(args.url, safe=safe)
    else:
        raise Error("No url specified")

    if "query" in args:
        out.serialised = urllib.parse.urlencode(args.query)
        out.url = "?".join((out.base, out.serialised))
    else:
        out.url = out.base
    return out

@service(web)
def content_type(args):
    out = duxlot.Storage()
    out.mime = None
    out.encoding = None

    regex_key = re.compile(r'([^=]+)')
    regex_value = re.compile(r'("[^"\\]*(?:\\.[^"\\]*)*"|[^;]+)')

    def parse(parameters):
        while parameters:
            match = regex_key.match(parameters)
            if not match:
                break

            key = match.group(1)
            parameters = parameters[len(key):]
            if parameters.startswith("="):
                parameters = parameters[1:]

            match = regex_value.match(parameters)
            if not match:
                break

            value = match.group(1)
            if value.startswith('"'):
                value = value[1:-1].replace('\\"', '"')
            parameters = parameters[len(value):]

            if parameters.startswith(";"):
                parameters = parameters[1:]

            key = key.lower().strip(" \t")
            value = value.lower().strip(" \t")
            yield key, value

    if "content-type" in args.headers:
        header = args.headers["content-type"]
        if ";" in header:
            out.mime, parameters = header.split(";", 1)
        else:
            out.mime, parameters = header, ""

        for key, value in parse(parameters):
            if key == "charset":
                out.encoding = value
                break
    return out

@service(web)
def default_user_agent(args):
    if "headers" in args:
        headers = args.headers
        if not "User-Agent" in headers: # @@ case sensitivity, etc.
            headers["User-Agent"] = web.options.default_user_agent
        return headers
    raise Error("Expected headers")

@service(web)
def head_summary(args):
    out = duxlot.Storage()
    page = web.request(**args())
    # hmm:
    s = web.headers_summary(status=page.status, headers=page.headers)
    out.headers = s("headers")
    out.mime = s("mime")
    out.encoding = s("encoding")
    out.modified = s("modified")
    out.length = s("length")
    out.summary = s("summary")
    return out

@service(web)
def headers_summary(args):
    out = duxlot.Storage()
    out.headers = args.headers

    if "content-type" in args.headers:
        content_type = args.headers["content-type"]

        if ";" in content_type:
            mime, charset = content_type.split(";")
        else: mime, charset = content_type, ""

        if "=" in charset:
            charset = charset.split("=").pop()

        out.mime = mime
        out.encoding = charset
        # @@ there's stuff for this in web.request

    if "last-modified" in args.headers:
        modified = args.headers["last-modified"]
        modified = time.strptime(modified, '%a, %d %b %Y %H:%M:%S %Z')
        out.modified = time.strftime('%Y-%m-%d %H:%M:%S UTC', modified)

    if "content-length" in args.headers:
        out.length = args.headers["content-length"]

    out.summary = str(args.status)
    for property in ("mime", "encoding", "modified", "length"):
        if property in out:
            out.summary += ", " + str(getattr(out, property))
            if property == "length":
                out.summary += " bytes"
    return out

@service(web)
def paste(args):
    page = web.request(
        url="http://dpaste.de/api/",
        data={"content": args.text}
    )
    return page.text.strip('"') + "raw/"

@service(web)
def request(args):
    out = duxlot.Storage()
    out.request_headers = web.default_user_agent(
        headers=args("headers", {})
    )

    out.request_url = web.construct_url(**args()).url

    class ErrorHandler(urllib.request.HTTPDefaultErrorHandler):
        def http_error_default(self, req, fp, code, msg, hdrs):
            return fp

    handlers = [ErrorHandler()]
    if not ("follow" in args):
        class RedirectHandler(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, hdrs, newurl):
                return None
        handlers.append(RedirectHandler())

    opener = urllib.request.build_opener(*handlers)
    urllib.request.install_opener(opener)

    params = {
        "url": out.request_url,
        "headers": out.request_headers
    }

    if "data" in args:
        data = args.data
        if isinstance(data, dict):
            data = urllib.parse.urlencode(data)
            params["data"] = data.encode("utf-8", "replace")
        elif isinstance(data, bytes):
            params["data"] = data
        elif isinstance(data, str):
            params["data"] = data.encode("utf-8", "replace")
        else:
            raise Error("Unknown data type: %s" % type(data))

    req = urllib.request.Request(**params)
    with urllib.request.urlopen(req) as response:
        out.status = response.status # int
        out.url = response.url

        if "method" in args:
            if args.method == "HEAD":
                # @@ support duplicates, somehow
                out.headers = py.dict_lower(dict=response.info(), discard=True)
            elif args.method == "GET":
                if not ("limit" in args):
                    out.octets = response.read()
                else:
                    out.octets = response.read(args.limit)
        else:
            # @@ support duplicates, somehow
            # also, this code could probably be refactored
            out.headers = py.dict_lower(dict=response.info(), discard=True)
            if not ("limit" in args):
                out.octets = response.read()
            else:
                out.octets = response.read(args.limit)

    if "headers" in out:
        info = web.content_type(headers=out.headers)
        if info("mime"):
            out.mime = info.mime

        if ("encoding" in info) and info.encoding:
            out.encoding = info.encoding
            out.encoding_source = "Content-Type"

        if info("mime") and ("octets" in out):
            if ("/html" in info.mime) or ("/xhtml" in info.mime):
                # Note that (?i) does work in byte instances
                p = b"(?i)<meta[^>]+charset=[\"']?([^\"'> \r\n\t]+)"
                regex_charset = re.compile(p)
                search = regex_charset.search(out.octets)
                if search:
                    encoding = search.group(1).lower()
                    encoding = encoding.decode("ascii", "replace")
                    if ("encoding" in out) and (encoding == out.encoding):
                            out.encoding_source += ", HTML"
                    else:
                        out.encoding = encoding
                        out.encoding_source = "HTML"

    if "octets" in out:
        def guess_encoding(out):
            try: out.text = out.octets.decode("iso-8859-1")
            except UnicodeDecodeError:
                out.text = out.octets.decode("utf-8", "replace")
                out.encoding = "utf-8"
            else:
                out.encoding = "iso-8859-1"
            out.encoding_source = "heuristic"

        if "encoding" in out:
            try: out.text = out.octets.decode(out.encoding)
            except (UnicodeDecodeError, LookupError):
                guess_encoding(out)
        else:
            guess_encoding(out)

    if ("mime" in out) and ("text" in out):
        if ("/html" in out.mime) or ("/xhtml" in out.mime):
                if not args("rawhtml"):
                    out.text = html.decode_entities(html=out.text)
                    out.decoded_entities = True

    return out

@service(web)
def title(args):
    regex_title = re.compile(r"(?ims)<title>(.*?)</title>")
    page = web.request(
        limit=262144,
        **args()
    )
    search = regex_title.search(page.text)
    if search:
        title = search.group(1)
        return html.scrape(html=title).strip()
    raise Error("No title found")

web.options = duxlot.Storage()
web.options.default_user_agent = "Mozilla/5.0 (Services)"


### Module: Wikipedia ###

wikipedia = duxlot.Storage()
wikipedia.name = "wikipedia"

@service(wikipedia)
def article(args):
    # (str) term: Required
    # (str) language: Optional
    out = duxlot.Storage()
    term = args.term
    language = args("language") or "en"
    debug = []

    def underscored(term):
        return term.replace(" ", "_")

    def spaced(term):
        return term.replace("_", " ")

    def search(term):
        debug.append("Searched %s for %r" % (language, spaced(term)))
        return wikipedia.article_search(
            term=spaced(term),
            language=language
        )

    upper = tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    lower = tuple("abcdefghijklmnopqrstuvwxyz")
    abbreviations = upper + lower + ("etc", "ca", "cf", "Co", "Ltd", "Inc",
        "Mt", "Mr", "Mrs", "Dr", "Ms", "Rev", "Fr", "St", "Sgt", "pron",
        "approx", "lit", "syn", "transl", "sess", "fl", "Op", "Dec", "Brig",
        "Gen", "Bros")
    abbreviations_pattern = r"(?<!\b%s)" % r")(?<!\b".join(abbreviations)
    regex_sentence= re.compile(
        r"^(.{5,}?%s(?:\.(?=[\[ ][A-Z0-9]|\Z)|\Z|\n))" % abbreviations_pattern
    )

    regex_block = re.compile(r"(?ims)<p[^>]*>.*?</p>|<li(?!n)[^>]*>.*?</li>")
    regex_tr = re.compile(r"(?ims)<tr.*?</(tr|table)>")
    regex_footnote = re.compile(r"[|]*\[[0-9]+\][|]*")

    def skip_html_block(block):
        skip = ("technical limitations", "window.showTocToggle",
            "Deletion_policy", "Template:AfD_footer",    'disambiguation)"',
            "(images and media)", "This article contains a",
            'id="coordinates"', 'class="thumb'    ,
            "using the Article Wizard if you wish", "or add a request for it",
            "in existing articles")

        if not block:
            return True
        if block.startswith("<p><i>") and block.endswith("</i></p>"):
            return True
        for text in skip:
            if text in block:
                return True

        return False

    def skip_text_block(block):
        # if block.endswith(":") and (len(block) < 150):
        #     return True
        if len(block) < 32:
            return True
        if not block:
            return True
        return False

    def scrape(block):
        block = block.replace("<sup>", "|")
        block = block.replace("</sup>", "|")
        block = html.scrape(html=block).strip()
        return regex_footnote.sub("", block)

    for attempt in range(2):
        # See if the article actually exists first, with following on
        page = web.request(
            url="https://%s.wikipedia.org/wiki/%s" % 
                (language, underscored(term)),
            follow=True
        )

        # @@ it's an int here? huh
        if page.status != 200:
            debug.append("%s gave %s" % (page.url, page.status))
            term = search(term)
            continue

        # Don't think they have those old 200 Redirects now
        text = regex_tr.sub("", page.text)
        blocks = regex_block.findall(text)
        if not blocks:
            debug.append("%s had no blocks" % page.url)
            term = search(term)
            continue

        # Filter out stuff we don't want
        blocks = (block for block in blocks if not skip_html_block(block))
        blocks = (scrape(block) for block in blocks)
        blocks = (block for block in blocks if not skip_text_block(block))

        block = next(blocks)
        try: block += " " + next(blocks) + " " + next(blocks)
        except StopIteration:
            ...

        sentence_match = regex_sentence.match(block)
        if not sentence_match:
            debug.append("%s had no sentences" % page.url)
            term = search(term)
            continue

        sentence = sentence_match.group(1)
        if 'href="/wiki/Category:Disambiguation_pages"' in page.text:
            sentence = "[Disambiguation] " + sentence

        if     len(sentence) < 128:
            block = block[len(sentence):].lstrip()
            sentence_match2 = regex_sentence.match(block)
            if sentence_match2:
                sentence += " " + sentence_match2.group(1)

        maxlength = 275
        if len(sentence) > maxlength: 
            words = sentence[:maxlength][:-6].split(" ")
            sentence = " ".join(words[:-1]) + " [...]"
        sentence = sentence.replace('"', "'")
        if sentence.endswith(":"):
            sentence = sentence[:-1] + "..."

        out.url = page.url
        out.term = spaced(term)
        out.sentence = sentence
        return out

    raise Error("Article not found: " + " | ".join(debug))

@service(wikipedia)
def article_search(args):
    site = "%s.wikipedia.org" % args("language", "en")
    term = args.term.replace("_", " ")
    phrase = "site:%s %s" % (site, term)
    url = google.search_api(phrase=phrase)
    if "?" in url:
        url = url.split("?", 1)[0]
    return url[len("http://%s/wiki/" % site):].replace("_", " ")


### Module: Word ###

word = duxlot.Storage()
word.name = "word"

@service(word)
def etymology(args):
    out = duxlot.Storage()
    pattern_sentence = \
        r"^(.*?(?<!%s)(?:\.(?= [A-Z0-9]|\Z)|\Z))" % ")(?<!".join((
        "cf", "lit", "etc", "Ger", "Du", "Skt", "Rus", "Eng", "Amer.Eng", "Sp",
        "Fr", "N", "E", "S", "W", "L", "Gen", "J.C", "dial", "Gk", "19c",
        "18c", "17c", "16c", "St", "Capt", "obs", "Jan", "Feb", "Mar", "Apr",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "c", "tr", "e", "g"
    ))
    regex_sentence = re.compile(pattern_sentence)
    regex_definition = re.compile("(?ims)<dd[^>]*>.*?</dd>")

    page = web.request(
        url="http://etymonline.com/index.php",
        query={"term": args.term},
        headers={"Referer": "http://www.etymonline.com/"}
    )

    if not "text" in page:
        raise Error("No response from %s" % page.url)

    definitions = regex_definition.findall(page.text)
    if not definitions:
        raise Error("No definitions found in %s" % page.url)

    definition = html.scrape(html=definitions[0])
    match = regex_sentence.match(definition)
    if not match:
        raise Error("No sentences found in definition")

    sentence = match.group(1)
    if "limit" in args:
        maxlength = args.limit - len(page.url) - len('"" - ')
        comment = """
  File "[...]/duxlot/api.py", line 2107, in etymology
    maxlength = args.limit - len(page.url) - len('"" - ')
TypeError: unsupported operand type(s) for -: 'NoneType' and 'int'
"""
    else:
        maxlength = 275

    if len(sentence) > maxlength: 
        words = sentence[:maxlength - 6].split(" ")
        sentence = " ".join(words[:-1]) + " [...]"

    out.url = page.url
    out.sentence = sentence.replace('"', "'")
    return out

@service(word)
def leo(args):
    out = duxlot.Storage()
    page = web.request(
        url="http://dict.leo.org/ende",
        query={"search": args.term}
    )

    regex_whitespace = re.compile(r"[ \t\r\n\xA0]+")
    regex_td = re.compile(r'<td valign="middle" width="43%">(.*?)</td>')

    def normalise(text):
        text = html.scrape(html=text)
        text = text.replace("(Brit.)", "")
        text = text.replace("adj.", "a.")
        text = text.replace("[", "(")
        text = text.replace("]", ")")
        return regex_whitespace.sub(" ", text.strip())

    definitions = [normalise(td) for td in regex_td.findall(page.text)]
    pairs = zip(definitions[::2], definitions[1::2])
    pairs = [(a, b) for a, b in pairs if not '(Amer.)' in a and not '(Amer.)' in b]

    order = []
    translations = {}

    for a, b in pairs: 
        if args.term in b: 
            a, b = b, a

        try: translations[a].append(b)
        except KeyError: 
            order.append(a)
            translations[a] = [b]

    result = []
    for entry in order[:5]: 
        result.append(entry + " = " + ", ".join(translations[entry][:5]))
        result[-1] = result[-1].replace(" | ", ", ").strip(" ,|")

    out.results = result
    out.text = " / ".join(result)
    out.url = page.url
    return out

@service(word)
def rhymes(args):
    if not args.word.isalpha():
        raise Error("Word must be alphabetical only")

    ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_0) AppleWebKit/537.1 "
    ua += "(KHTML, like Gecko) Chrome/21.0.1180.82 Safari/537.1"

    page = web.request(
        url="http://www.rhymezone.com/r/rhyme.cgi",
        query={
            "Word": args.word,
            "typeofrhyme": "perfect",
            # "org1": "syl",
            # "org2": "l",
            # "org3": "y"
        },
        headers={
            "user-agent": ua,
            # "referer": "http://www.rhymezone.com/"
        }
    )

    if "was not found" in page.text:
        return "Can't find words that rhyme with %s" % args.word

    results = []
    length = 0
    text = page.text.split("syllable", 1).pop()
    text = text.split("<hr", 1)[0]

    for bold in re.findall("(?i)<b>(.*?)</b>", text):
        word = html.scrape(html=bold)
        if word == "Word:":
            return "Can't find words that rhyme with %s" % args.word

        if (" " in word) or ("\xA0" in word):
            continue

        results.append(word)
        length += len(word) + 2
        if length >= 256:
            results.append("...")
            break

    return ", ".join(results) + " (rhymezone.com)"

@service(word)
def thesaurus(args):
    if not args.word.isalpha():
        raise Error("Word must be alphabetical only")

    ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_0) AppleWebKit/537.1 "
    ua += "(KHTML, like Gecko) Chrome/21.0.1180.82 Safari/537.1"

    page = web.request(
        url="http://thesaurus.com/browse/" + args.word.lower(),
        query={"s": "t"},
        headers={
            "user-agent": ua,
            # "referer": "http://www.rhymezone.com/"
        }
    )

    page = page.text
    if "Concept Thesaurus" in page:
        page = page.split("Concept Thesaurus")[0]

    findall = re.findall("(?ims)Synonyms:</td>(.*?)</td>", page)
    if not findall:
        return "Can't find synonyms of %s" % args.word

    findall = sorted(findall, key=len)
    synonyms = findall.pop()

    text = html.scrape(html=synonyms)
    text = text.replace(", ", ",").replace(",", ", ").replace("*", "")
    return text.strip()[:256] + " (thesaurus.com)"

@service(word)
def wiktionary(args):
    article = word.wiktionary_article(**args())
    return word.wiktionary_format(**article())

@service(word)
def wiktionary_article(args):
    out = duxlot.Storage()
    regex_wiktionary_ul = re.compile(r"(?ims)<ul>.*?</ul>")

    def text(input):
        text = html.scrape(html=input)
        text = text.replace("\n", " ")
        text = text.replace("\r", "")
        text = text.replace("(intransitive", "(intr.")
        text = text.replace("(transitive", "(trans.")
        return text

    page = web.request(
        url="http://en.wiktionary.org/w/index.php",
        query={"title": args.word, "printable": "yes"}
    )

    content = page.text
    content = regex_wiktionary_ul.sub("", content)

    mode = None
    etymology = None
    definitions = {}
    for line in content.splitlines():
        if 'id="Etymology"' in line: 
            mode = "etymology"
        elif 'id="Noun"' in line: 
            mode = "noun"
        elif 'id="Verb"' in line: 
            mode = "verb"
        elif 'id="Adjective"' in line: 
            mode = "adjective"
        elif 'id="Adverb"' in line: 
            mode = "adverb"
        elif 'id="Interjection"' in line: 
            mode = "interjection"
        elif 'id="Particle"' in line: 
            mode = "particle"
        elif 'id="Preposition"' in line: 
            mode = "preposition"
        elif 'id="' in line: 
            mode = None

        elif (mode == "etmyology") and ("<p>" in line):
            etymology = text(line)
        elif (mode is not None) and ("<li>" in line):
            definitions.setdefault(mode, []).append(text(line))

        if "<hr" in line: 
            break

    out.word = args.word
    out.etymology = etymology
    out.definitions = definitions
    return out

@service(word)
def wiktionary_format(args):
    number = args("number", 2)
    parts = ("preposition", "particle", "noun", "verb", 
        "adjective", "adverb", "interjection")

    result = args.word
    for part in parts: 
        if part in args.definitions:
            defs = args.definitions[part][:number]
            result += " — " + ('%s: ' % part)
            n = ["%s. %s" % (i + 1, e.strip(" .")) for i, e in enumerate(defs)]
            result += ", ".join(n)

    return result.strip(" .,")

if __name__ == "__main__":
    ...
