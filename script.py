# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

import sys

# Require 3.2.2 because of http://bugs.python.org/issue12576
if sys.version_info < (3, 2, 2):
    print("Error: Requires python 3.2.2 or later")
    sys.exit(1)

import argparse
import atexit
import os
import signal

import duxlot

signal.signal(signal.SIGHUP, signal.SIG_IGN)

# Turn off buffering, like python3 -u
# http://stackoverflow.com/questions/107705

ourpid = None

class Unbuffered:
    def __init__(self, stream):
        self.stream = stream # @@ __stream

    def write(self, data):
        try:
            self.stream.write(data)
            self.stream.flush()
        except IOError:
            import multiprocessing
            multiprocessing.sys.stdout = self
            multiprocessing.sys.stderr = self

            self.write = lambda data: ...

            # Possibly make this SIGUSR1
            try: os.kill(ourpid, signal.SIGUSR1)
            except OSError:
                ...

    def __getattr__(self, attr):
        return getattr(self.stream, attr)

sys.stdout = Unbuffered(sys.stdout)
sys.stderr = Unbuffered(sys.stderr)

def action(function):
    action.names[function.__name__] = function
    return function
action.names = {}

def writeable(path):
    if os.path.exists(path):
        return os.access(path, os.W_OK)

    directory = os.path.dirname(path)
    if not os.path.isdir(directory):
        return False

    return os.access(directory, os.W_OK)

def fork(n):
    try: pid = os.fork()
    except OSError as err:
        print("Error: Unable to fork on this OS: %s" % err)
        print("Use the --foreground option to avoid running as a daemon")
        sys.exit(1)
    else:
        if pid > 0:
            sys.exit(0)

def redirect(a, b):
    os.dup2(b.fileno(), a.fileno())

def only(args, targets):
    others = set(vars(args).keys()) - targets
    return not any(getattr(args, other) for other in others)

def daemonise(args):
    if args.output is None:
        args.output = open(os.devnull, "w")
    elif args.output in {"-", "/dev/stdout"}:
        args.output = sys.stdout
    else:
        args.output = open(args.output, "w")

    if not writeable(args.pidfile):
        print("Error: Can't write to PID file: " + str(args.pidfile))
        sys.exit(1)

    fork(1)

    os.chdir("/")
    os.setsid()
    os.umask(0)

    fork(2)

    pid = os.getpid()

    print("Running duxlot as PID %s" % pid)
    print("The PID will be saved to %s" % args.pidfile)

    sys.stdout.flush()
    sys.stderr.flush()

    redirect(sys.stdin, open(os.devnull, "r"))
    redirect(sys.stdout, args.output)
    redirect(sys.stderr, args.output)

    with duxlot.filesystem.open(args.pidfile, "w") as f:
        f.write(str(pid) + "\n")

    def delete_pidfile():
        if os.path.isfile(args.pidfile):
            os.remove(args.pidfile)

    atexit.register(delete_pidfile)

    return pid

def running(pid):
    import errno

    try: os.kill(pid, 0)
    except OSError as err:
        return err.errno != errno.ESRCH
    else:
        return True

def read_pidfile(name):
    try:
        with duxlot.filesystem.open(name, "r") as f:
            text = f.read()
        number = text.lstrip("\n")
        return int(number)
    except Exception as err:
        print("Couldn't read the PID file: %s: %s" % (args.pidfile, err))
        sys.exit(1)

def clean_pidfile(name, pid):
    print("Warning: The previous PID file had not been removed")
    print("Warning: The PID was recorded as %s" % pid)
    print("Warning: This may mean duxlot did not exit cleanly")
    os.remove(name)

def resolve(identifier):
    def resolve_path(path):
        path = os.path.expanduser(path)
        return os.path.abspath(path)

    def resolve_alias(alias):
        alias = "default" if (alias is None) else alias
        return duxlot.config.aliases.get(alias)

    if identifier is None:
        if duxlot.config.aliases.exists():
            if duxlot.config.aliases.exists("default"):
                return duxlot.config.aliases.get("default")

        if duxlot.config.exists(duxlot.config.default):
            return duxlot.config.default

        print("Error: No default configuration file to use")
        print("You can create one using:")
        print("")
        print("    duxlot create")
        print("")
        print("Or by setting a default alias:")
        print("")
        print("    duxlot alias <path> default")
        sys.exit(1)

    if "/" in identifier:
        return resolve_path(identifier)

    path = resolve_path(identifier)
    path_exists = os.path.isfile(path)
    if duxlot.config.aliases.exists():
        alias_exists = duxlot.config.aliases.exists(identifier)
    else:
        alias_exists = False

    if path_exists and (not alias_exists):
        return path

    if alias_exists and (not path_exists):
        return resolve_alias(identifier)

    if path_exists and alias_exists:
        print("Error: %s is both a path and an alias!" % identifier)
        print("If you'd prefer one to be used as a default, open an issue:")
        print("https://github.com/sbp/duxlot/issues/new")
        sys.exit(1)

    # Neither path_exists nor alias_exists
    print("Error: %s is neither a valid path nor a known alias" % identifier)
    sys.exit(1)

comment = '''
def check_current():
    # @@ import api

    page = api.web.request(
        url="https://raw.github.com/sbp/duxlot/master/data/version"
    )

    if page.mime == "text/plain":
        current = page.text.rstrip()
    
        that = tuple(int(n) for n in current.replace("-", ".").split("."))
        this = tuple(int(n) for n in duxlot.version.replace("-", ".").split("."))
    
        if this < that:
            print("""\
=== WARNING ===

This version of duxlot (%s) is out of date!

Download the latest version (%s) here:

http://pypi.python.org/packages/source/d/duxlot/duxlot-%s.tar.bz2

Or get the source from Github:

https://github.com/sbp/duxlot

Using the latest version helps the maintainer to get better feedback.

In versions which are not alpha quality, this message will be reduced,
and a config file option may be enabled to turn such messages off.
""" % (duxlot.version, current, current))
'''

@action
def alias(args):
    "Set an alias for a configuration file"
    if not only(args, {"action", "identifier", "alias"}):
        print("Error: Usage: duxlot alias <path> [<alias>]")
        sys.exit(1)

    if not args.identifier:
        print("Error: You must specify a <path> to alias")
        sys.exit(1)

    if not args.alias:
        # print("Error: @@ Not yet implemented")
        print("Error: You must specify an <alias> to set")
        sys.exit(1)

    if not duxlot.config.aliases.exists():
        duxlot.config.aliases.create()

    existed = duxlot.config.aliases.exists(args.alias)
    if existed is True:
        verb = "Changed alias"
        was = duxlot.config.aliases.get(args.alias)
        if was == args.identifier:
            print("Error: Alias %r is already set to %r" % (args.alias, args.identifier))
            return 1
    else:
        verb = "Aliased"

    duxlot.config.aliases.put(args.alias, args.identifier)
    print("%s %r to %r" % (verb, args.alias, args.identifier))
    if existed is True:
        print("Was previously set to %r" % was)
    return 0

@action
def unalias(args):
    "Remove an alias for a configuration file"
    if not only(args, {"action", "identifier"}):
        print("Error: Usage: duxlot unalias <alias>")
        sys.exit(1)

    if not args.identifier:
        print("Error: You must specify an <alias> to remove")
        sys.exit(1)

    if not duxlot.config.aliases.exists():
        print("Error: The alias %r is not currently set" % args.identifier)
        print("There are no currently set aliases")
        return 1

    if not duxlot.config.aliases.exists(args.identifier):
        print("Error: The alias %r is not currently set" % args.identifier)
        return 1

    value = duxlot.config.aliases.get(args.identifier)
    duxlot.config.aliases.remove(args.identifier)
    print("Removed the alias %r" % args.identifier)
    print("Was previously set to %r" % value)
    return 0

@action
def active(args):
    "Check whether the specified duxlot instance is running"
    if not only(args, {"action", "identifier"}):
        print("Error: Usage: duxlot active [<path-or-alias>]")
        sys.exit(1)

    config = resolve(args.identifier)
    filename, base, data = duxlot.config.info(config)
    args.pidfile = base + ".pid"

    # Does the PID file already exist?
    if os.path.isfile(args.pidfile):
        pid = read_pidfile(args.pidfile)
        if running(pid):
            print("duxlot is already running as PID %s" % pid)
            print("Base:", duxlot.config.reduceuser(base))
            return 0
        else:
            print("duxlot is not running")
            print("Base:", duxlot.config.reduceuser(base))
            clean_pidfile(args.pidfile, pid)
            print("Warning: There was a PID file, now cleaned")
            return 0
    elif os.path.exists(args.pidfile):
        message = "PID file path exists but is not a regular file"
        print("Error: %s: %s" % (message, args.pidfile))
        return 1
    else:
        print("duxlot is not running")
        print("Base:", duxlot.config.reduceuser(base))
        return 0

@action
def config(args):
    "Show the config file associated with a particular alias"
    if not only(args, {"action", "identifier"}):
        print("Error: Usage: duxlot config <alias>")
        sys.exit(1)

    config = resolve(args.identifier)
    print(args.identifier, "=", config)

def help():
    print("""\
Usage:

    duxlot --version - Show the current duxlot version
    duxlot --actions - Show more documentation for available actions
    duxlot --console - Run a limited term console version of duxlot

Control actions:

    duxlot [ --<flags> ] start [<identifier>]
        --foreground - don't run the bot as a daemon
        --output <path> - redirect stdout and stderr to <path>
    duxlot stop [<identifier>]
    duxlot restart [<identifier>]
    duxlot active [<identifier>]

Configuration actions:

    duxlot create
    duxlot alias <path> <alias>
    duxlot unalias <alias>
    duxlot config <identifier>
""")

def actions():
    print("""\
Control actions:

    duxlot [FLAGS] start [<identifier>]
        Starts a bot. Optional [FLAGS]:

            --foreground - Don't run the bot as a daemon
            --output <path> - Redirect stdout and stderr to <path>

        An <identifier> is a relative or absolute path, or an alias.
        The value of "duxlot config" will be used by default.

    duxlot stop [<identifier>]
        Stops a bot

    duxlot restart [<identifier>]
        Restarts a bot. Calls stop then start

    duxlot active [<identifier>]
        Shows whether a bot is active

Configuration actions:

    duxlot create
        Create a default configuration file

    duxlot alias <path> <alias>
        Set <alias> as an alias of <path>

    duxlot unalias <alias>
        Remove <alias> if it exists

    duxlot config <identifier>
        Show the config file referred to by <identifier>
""")

@action
def start(args):
    "Start the specified duxlot instance"
    global ourpid

    if not only(args, {"foreground", "output", "action", "identifier"}):
        print("Error: Usage: duxlot [-f] [-o] start [<path-or-alias>]")
        sys.exit(1)

    import multiprocessing

    # Semaphores are used in JoinableQueue, and possibly other things
    try: multiprocessing.Semaphore()
    except OSError as err:
        print("Oh dear, your system might not allow POSIX Semaphores")
        print("See http://stackoverflow.com/questions/2009278 to fix")
        return 1

    config = resolve(args.identifier)
    filename, base, data = duxlot.config.info(config)
    args.pidfile = base + ".pid"

    # Does the PID file already exist?
    if os.path.isfile(args.pidfile):
        pid = read_pidfile(args.pidfile)
        if running(pid):
            print("Error: duxlot is already running as PID %s" % pid)
            print("Try running 'stop' or 'restart'")
            return 1
        else:
            clean_pidfile(args.pidfile, pid)
    elif os.path.exists(args.pidfile):
        message = "PID file path exists but is not a regular file"
        print("Error: %s: %s" % (message, args.pidfile))
        return 1

    if not args.foreground:
        daemonise(args)
        ourpid = os.getpid()
    else:
        ourpid = os.getpid()
        print("Running as PID", ourpid)

    duxlot.client(filename, base, data)

@action
def stop(args):
    "Stop the specified duxlot instance"
    if not only(args, {"action", "identifier"}):
        print("Error: Usage: duxlot stop [<path-or-alias>]")
        sys.exit(1)

    config = resolve(args.identifier)
    filename, base, data = duxlot.config.info(config)
    args.pidfile = base + ".pid"

    if os.path.isfile(args.pidfile):
        pid = read_pidfile(args.pidfile)
        if running(pid):
            import time

            os.kill(pid, signal.SIGTERM)
            print("Sent SIGTERM to PID %s" % pid)
            start = time.time()
            while time.time() < (start + 20):
                if not running(pid):
                    print("Successfully stopped PID %s" % pid)
                    if os.path.isfile(args.pidfile): # should fix dpk's error
                        os.remove(args.pidfile)
                    return 0
                time.sleep(0.5)

            print("Warning: PID %s did not quit within 20 seconds" % pid)
            os.kill(pid, signal.SIGKILL)
            if os.path.isfile(args.pidfile):
                os.remove(args.pidfile)
            print("Sent a SIGKILL, and removed the PID file manually")
            return 1
        else:
            clean_pidfile(args.pidfile, pid)
            return 1
    elif os.path.exists(args.pidfile):
        message = "PID file path exists but is not a regular file"
        print("Error: %s: %s" % (message, args.pidfile))
        return 1
    else:
        print("Error: duxlot is not running")
        return 1

@action
def restart(args):
    "Restart the specified duxlot instance"
    if not only(args, {"action", "identifier"}):
        print("Error: Usage: duxlot restart [<path-or-alias>]")
        sys.exit(1)

    code = stop(args)
    if code != 0:
        print("Warning: Exiting without starting the bot")
        return 1
    return start(args)

@action
def create(args):
    "Create a default configuration file to work from"
    if not only(args, {"action"}):
        print("Error: Expected only 'create', no other options")
        sys.exit(1)

    if not duxlot.config.exists(duxlot.config.default):
        duxlot.config.create()
        print("You may now edit this default configuration, then run the bot:")
        print("")
        print("    $ duxlot start")
        sys.exit(0)
    else:
        print("Error: The default configuration file already exists:")
        print("")
        print("   " + duxlot.config.default)
        sys.exit(1)

# @@ unused
def act(args):
    if not only(args, {"act"}):
        print("Error: Expected only --act, no other options")
        sys.exit(1)

    action_documentation = []
    for action_name in sorted(action.names):
        documentation = action.names[action_name].__doc__
        doc = "%s - %s" % (action_name, documentation)
        action_documentation.append(doc)
    action_documentation = "\n".join(action_documentation)
    print("The following actions are available:")
    print()
    print(action_documentation)
    return 0

# @@ undocumented?
@action
def options(args):
    "Show valid duxlot configuration file option names"
    # @@ --options? oh, but -o. -d --documentation?
    if not only(args, {"action"}):
        print("Error: Expected only 'options', no other options")
        sys.exit(1)

    for (option, info) in sorted(duxlot.config.options.items()):
        if info.public:
            print("%s: %s" % (option, info.documentation))

def version(args):
    if not only(args, {"version"}):
        print("Error: Expected only --version, no other options")
        sys.exit(1)

    print("duxlot", duxlot.version)

def console(args):
    if not only(args, {"console"}):
        print("Error: Expected only --console, no other options")
        sys.exit(1)

    # Save PEP 3122!
    if "." in __name__:
        from . import console
    else:
        import console

    # @@ suppress the load warnings
    console.main()

# @@ an "aliases" action, to show all aliases

def doc(text, local):
    combined = dict(globals(), **local)
    print(text.strip("\r\n").format(**combined))

def unrecognised(action):
    doc("""
Unrecognised action: {action}

Try viewing a list of valid actions:

    {sys.argv[0]} --actions

Or, to view a list of options:

    {sys.argv[0]} --help
""", vars())
    sys.exit(1)

def default():
    doc("""
To create a default configuration file to start from:

    {sys.argv[0]} create

Or, to view a list of options:

    {sys.argv[0]} --help
""", vars())

# @@ config action, shows config belonging to alias

def main():
    parser = argparse.ArgumentParser(
        description="Control duxlot IRC bot instances",
        add_help=False
    )

    parser.add_argument(
        "-c", "--console",
        help="use a limited version of duxlot as a term console",
        action="store_true"
    )
    parser.add_argument(
        "-f", "--foreground",
        help="run in the foreground instead of as a daemon",
        action="store_true"
    )
    parser.add_argument(
        "-h", "--help",
        help="show a short help message",
        action="store_true"
    )
    parser.add_argument(
        "-o", "--output",
        metavar="FILENAME",
        help="redirect daemon stdout and stderr to this filename"
    )
    parser.add_argument(
        "--actions",
        help="show a long help message about actions",
        action="store_true"
    )
    parser.add_argument(
        "-v", "--version",
        help="show the current duxlot version",
        action="store_true"
    )
    parser.add_argument(
        "action",
        help="use --actions to show the available actions",
        nargs="?"
    )
    parser.add_argument(
        "identifier",
        help="the path or alias of the configuration file to use",
        nargs="?"
    )
    parser.add_argument(
        "alias",
        help="the alias to use in the corresponding action",
        nargs="?"
    )
    args = parser.parse_args()

    if args.help:
        help()

    elif args.actions:
        actions()

    elif args.version:
        version(args)

    elif args.console:
        console(args)

    elif args.action:
        if args.action in action.names:
            code = action.names[args.action](args)
            if isinstance(code, int):
                sys.exit(code)
        else:
            unrecognised(args.action)

    elif not duxlot.config.exists(duxlot.config.default):
        default()

    else:
        help() # parser.print_help()
