# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

import argparse
import atexit
import os
import signal
import sys

import duxlot

signal.signal(signal.SIGHUP, signal.SIG_IGN)

if sys.version_info < (3, 2):
    print("Error: Requires python 3.2 or later")
    sys.exit(1)

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
        print("Error: Fork #%s failed: %s" % (n, err))
        sys.exit(1)
    else:
        if pid > 0:
            sys.exit(0)

def redirect(a, b):
    os.dup2(b.fileno(), a.fileno())

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

    with open(args.pidfile, "w") as f:
        f.write(str(pid) + "\n")

    def delete_pidfile():
        os.remove(args.pidfile)

    atexit.register(delete_pidfile)

def running(pid):
    import errno

    try: os.kill(pid, 0)
    except OSError as err:
        return err.errno != errno.ESRCH
    else:
        return True

def read_pidfile(name):
    try:
        with open(name, "r") as f:
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

def alias(args):
    "Set an alias for a configuration file"
    args.alias = "default" if (args.alias is None) else args.alias

    if not args.config:
        print("Error: You must also specify a config file to alias")
        print("Use the --config flag to pass a config filename")
        return 1

    if not duxlot.config.aliases.exists():
        duxlot.config.aliases.create()

    existed = duxlot.config.aliases.exists(args.alias)
    if existed is True:
        verb = "Changed alias"
        was = duxlot.config.aliases.get(args.alias)
        if was == args.config:
            print("Error: Alias %r is already set to %r" % (args.alias, args.config))
            return 1
    else:
        verb = "Aliased"

    duxlot.config.aliases.put(args.alias, args.config)
    print("%s %r to %r" % (verb, args.alias, args.config))
    if existed is True:
        print("Was previously set to %r" % was)
    return 0

def unalias(args):
    "Remove an alias for a configuration file"
    args.alias = "default" if (args.alias is None) else args.alias

    if not duxlot.config.aliases.exists():
        print("Error: The alias %r is not currently set" % args.alias)
        print("There are no currently set aliases")
        return 1

    if not duxlot.config.aliases.exists(args.alias):
        print("Error: The alias %r is not currently set" % args.alias)
        return 1

    value = duxlot.config.aliases.get(args.alias)
    duxlot.config.aliases.remove(args.alias)
    print("Removed the alias %r" % args.alias)
    print("Was previously set to %r" % value)
    return 0

def active(args):
    "Check whether the specified duxlot instance is running"
    config = config_from_args(args)
    if (config is None) and (not duxlot.config.exists(duxlot.config.default)):
        print("Error: No default configuration to use")
        return 1

    filename, base, data = duxlot.config.info(config)
    if args.where:
        print(filename)
        return 0

    args.pidfile = base + ".pid"

    # Does the PID file already exist?
    if os.path.isfile(args.pidfile):
        pid = read_pidfile(args.pidfile)
        if running(pid):
            print("duxlot is already running as PID %s" % pid)
            return 0
        else:
            print("duxlot is not running")
            clean_pidfile(args.pidfile, pid)
            print("Warning: There was a PID file, now cleaned")
            return 0
    elif os.path.exists(args.pidfile):
        message = "PID file path exists but is not a regular file"
        print("Error: %s: %s" % (message, args.pidfile))
        return 1
    else:
        print("duxlot is not running")
        return 0

def config_from_args(args):
    if args.alias is not None:
        if args.config:
            print("Mutually exclusive options: --config and [ alias ]")
            print("Couldn't choose between %r and %r" % (args.config, args.alias))
            return 1

        args.alias = args.alias or "default"
        config = duxlot.config.aliases.get(args.alias)
    elif (not args.config) and duxlot.config.aliases.exists():
        if duxlot.config.aliases.exists("default"):
            config = duxlot.config.aliases.get("default")
        else: config = args.config
    else:
        config = args.config
    return config

def start(args):
    "Start the specified duxlot instance"
    import multiprocessing

    config = config_from_args(args)
    if (config is None) and (not duxlot.config.exists(duxlot.config.default)):
        print("Error: No default configuration to use")
        return 1

    filename, base, data = duxlot.config.info(config)
    if args.where:
        print(filename)
        return 0

    args.pidfile = base + ".pid"

    # Semaphores are used in JoinableQueue, and possibly other things
    try: multiprocessing.Semaphore()
    except OSError as err:
        print("Oh dear, your system might not allow POSIX Semaphores")
        print("See http://stackoverflow.com/questions/2009278 to fix")
        return 1

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

    duxlot.client(filename, base, data)

def stop(args):
    "Stop the specified duxlot instance"
    config = config_from_args(args)
    if (config is None) and (not duxlot.config.exists(duxlot.config.default)):
        print("Error: No default configuration to use")
        return 1

    filename, base, data = duxlot.config.info(config)
    if args.where:
        print(filename)
        return 0

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
                    return 0
                time.sleep(0.5)

            print("Warning: PID %s did not quit within 20 seconds" % pid)
            os.kill(pid, signal.SIGKILL)
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

def restart(args):
    "Restart the specified duxlot instance"
    code = stop(args)
    if code != 0:
        print("Warning: Exiting without starting the bot")
        return 1
    return start(args)

def create(args):
    "Create a default configuration file to work from"
    if not duxlot.config.exists(duxlot.config.default):
        duxlot.config.create()
        print("You may now edit the default configuration")
        print("To run the bot, then do $ duxlot start")
        sys.exit(0)
    else:
        print("Error: The default configuration file already exists")
        print("   " + duxlot.config.default)
        sys.exit(1)

def actions(args):
    action_documentation = []
    for action in sorted(action_map):
        documentation = action_map[action].__doc__
        doc = "%s - %s" % (action, documentation)
        action_documentation.append(doc)
    action_documentation = "\n".join(action_documentation)
    print("The following actions are available:")
    print()
    print(action_documentation)
    return 0

def options(args):
    for (option, info) in sorted(duxlot.config.variables.items()):
        if info.public:
            print("%s: %s" % (option, info.documentation))

# @@ config option, shows config belonging to alias
action_map = {
    "create": create,
    "start": start,
    "stop": stop,
    "restart": restart,
    "alias": alias,
    "unalias": unalias,
    "active": active,
    "options": options
}

def main():
    description = "Control duxlot IRC bot instances"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "-a", "--actions",
        help="show all available actions and their effects",
        action="store_true"
    )
    parser.add_argument(
        "-c", "--config",
        metavar="FILENAME",
        help="use this JSON configuration file"
    )
    parser.add_argument(
        "-f", "--foreground",
        help="run in the foreground instead of as a daemon",
        action="store_true"
    )
    parser.add_argument(
        "-o", "--output",
        metavar="FILENAME",
        help="redirect daemon stdout and stderr to this filename",
        default=os.devnull
    )
    # @@ a "which" action
    parser.add_argument(
        "-w", "--where",
        help="don't run anything, show the config file that would be used",
        action="store_true"
    )
    parser.add_argument(
        "action",
        help="use --actions to show the available actions",
        nargs="?"
    )
    parser.add_argument(
        "alias",
        help="the alias of the config file to use",
        nargs="?"
    )
    args = parser.parse_args()

    if args.actions:
        actions(args)
    elif args.action:
        if args.action in action_map:
            code = action_map[args.action](args)
            if isinstance(code, int):
                sys.exit(code)
        else:
            print("Unrecognised action: " + str(args.action))
            print()
            print("Try viewing a list of valid actions:")
            print()
            print("   %s --actions" % sys.argv[0])
            print()
            print("Or, to view a list of options:")
            print()
            print("   %s --help" % sys.argv[0]) # parser.prog
            sys.exit(1)
    elif not duxlot.config.exists(duxlot.config.default):
        print("To create a default configuration file to start from:")
        print()
        print("   %s create" % sys.argv[0]) # parser.prog
        print()
        print("Or, to view a list of options:")
        print()
        print("   %s --help" % sys.argv[0]) # parser.prog
        sys.exit(0)
    else:
        parser.print_help()
