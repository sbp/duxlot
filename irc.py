#!/usr/bin/env python3

# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

"Main module"

import os.path
import multiprocessing
import signal
import socket
import sys
import time

import duxlot

# Save PEP 3122!
if "." in __name__:
    from . import api
    from . import process
else:
    import api
    import process

# @@ Could move this to storage.filesystem.modules(directory)
def modules_in_directory(directory):
    import glob
    names = []
    for name in glob.glob(os.path.join(directory, "*.py")):
        name = os.path.basename(name)
        names.append(name[:-3])
    return names

debug = duxlot.output.write

def task(method):
    name = method.__name__.rsplit("_", 1).pop()
    task.methods[name] = method
    return method
task.methods = {}

class Client(object):
    def __init__(self, name, base, data):
        self.check_semaphores()

        self.config = duxlot.FrozenStorage({
            "name": name,
            "base": base,
            "data": data
        })

        self.processes = process.Processes(self.create_socket)

        self.populate_safe()
        self.handle_signals()

        self.standard_directory = os.path.join(duxlot.path, "standard")

        self.load()
        self.setup()

        # process.SocketProcess calls this, no need to do it here
        # self.create_socket()
        self.start()
        self.tasks()

    def check_semaphores(self):
        try: multiprocessing.Semaphore()
        except OSError as err:
            debug("Oh dear, your system might not allow POSIX Semaphores")
            debug("See http://stackoverflow.com/questions/2009278 to fix")
            sys.exit(1)

    def populate_safe(self):
        self.safe = safe = duxlot.Storage()

        safe.manager = multiprocessing.Manager()
        safe.lock = multiprocessing.RLock()

        safe.tasks = self.processes.queue
        safe.sending = self.processes["send"].queue
        safe.messages = self.processes["messages"].queue
        safe.event_messages = self.processes["events"].queue
        safe.schedule = self.processes["schedule"].queue

        safe.data = safe.manager.dict()
        safe.options = safe.manager.dict(self.config.data)
        safe.commands = process.Commands(safe.manager, safe.schedule.put)

        db_base = self.config.data["database"]
        db_base = db_base.replace("$(BASE)", self.config.base)
        db_base = duxlot.config.path(db_base)

        safe.database = duxlot.database(db_base, safe.manager.Namespace())
        safe.send_message = create_send_message(safe.sending, debug)

        def log(*text):
            safe.tasks.put(("log",) + text)
        safe.log = log

    def handle_signals(self):
        # http://stackoverflow.com/questions/2549939
        signames = {}
        for name, number in signal.__dict__.items():
            if name.startswith("SIG") and not name.startswith("SIG_"):
                signames[number] = name

        # @@ Different handler for SIGTERM and SIGINT?
        # @@ Only run in process:main, using PID
        def terminate(signum, frame):
            # self.processes.empty()

            # @@ Actually could be another user sending the signal
            user = os.environ.get("USER", "a signal")
            signame = signames.get(signum, signum)
            message = "%s made me do it (%s)" % (user, signame)
            self.safe.send_message("QUIT", message)

            # This calls .finish(), so the QUIT above should work
            self.processes.stop()

            # Stop any stray commands, potentially corrupting queues
            try: self.safe.commands.collect(0)
            except: ...

            # Send SIGKILL to any remaining processes that we know of
            process.killall()

            # Since we're exiting, we don't need to mop up process queues
            os._exit(0)
        signal.signal(signal.SIGTERM, terminate)
        signal.signal(signal.SIGINT, terminate)

        def broken_script_pipe(signum, frame):
            try: self.processes[self.processes.socket].finish()
            except: ...
            process.killall()
            sys.exit() # Not os._exit
        signal.signal(signal.SIGUSR1, broken_script_pipe)

    def load(self):
        import importlib

        self.modules = {}

        standard = set(self.safe.options["standard"])
        directories = [self.standard_directory] + self.safe.options["user"]

        for directory in directories:
            module_names = modules_in_directory(directory)

            if directory == self.standard_directory:
                if standard != {"*"}:
                    module_names = standard & set(module_names)

            imported_names = []
            for module_name in module_names:
                if module_name in sys.modules:
                    debug("Warning: Skipping duplicate: %s" % module_name)
                    continue
                identifier = (module_name, directory)

                sys.path[:0] = [directory, duxlot.path]
                self.modules[identifier] = importlib.import_module(module_name)
                imported_names.append(module_name)
                sys.path[:2] = []

            # @@ reduce PWD too?
            udir = duxlot.config.reduceuser(directory)
            debug("Imported", ", ".join(imported_names), "from", udir)

    def reload(self, sender=None, nick=None):
        import imp

        def error(msg):
            if sender and nick:
                self.safe.send_message("PRIVMSG", sender, nick + ": " + msg)

        duxlot.clear()

        sys.path[:0] = [duxlot.path]
        imp.reload(api)
        sys.path[:1] = []

        for (module_name, directory), module in self.modules.items():
            sys.path[:0] = [directory, duxlot.path]

            try: reloaded = imp.reload(module)
            except Exception as err:
                message = "%s: %s" % (err.__class__.__name__, err)
                debug(message)
                error(message)

                return False
            else:
                self.modules[(module_name, directory)] = reloaded
            finally:
                sys.path[:2] = []

        return True

    def setup(self):
        # @@ Recording sources of commands
        for startup in duxlot.startups:
            startup(self.safe)

        self.safe.named = duxlot.commands.copy()
        self.safe.events = duxlot.events.copy()

    def start(self):
        self.processes["receive"].action(process_receive, self.safe)
        self.processes["send"].action(process_send, self.safe)
        self.processes["messages"].action(process_messages, self.safe)
        self.processes["events"].action(process_events, self.safe)
        self.processes["schedule"].action(process_schedule, self.safe)

        self.processes.start()

    def create_socket(self):
        sock = socket.socket(socket.AF_INET, socket.TCP_NODELAY)

        if self.safe.options["ssl"] is True:
            import ssl
            debug("Warning: Using SSL, but not validating the cert!")
            sock = ssl.wrap_socket(
                sock,
                server_side=False,
                cert_reqs=ssl.CERT_NONE # @@ or CERT_REQUIRED
            )

        address = (self.safe.options["server"], self.safe.options["port"])

        debug("Connecting to %s:%s" % address)
        try: sock.connect(address)
        except socket.error:
            debug("Connection refused to %s:%s" % address)

            # This sleep value is an irreducible minimum! It prevents crazy.
            # You might think that making this lower would be a good thing;
            # that would turn out not to be the case.
            time.sleep(3)
        return sock

    def tasks(self):
        self.main = duxlot.Storage()

        for name, method in task.methods.items():
            setattr(self.main, name, method)

        while True:
            parameters = self.safe.tasks.get()
            name, arguments = parameters[0], parameters[1:]
            debug("Got task:", name, arguments)

            if name in self.main:
                try: getattr(self.main, name)(self, *arguments)
                except Exception as err:
                    debug("Task Error:", name, err)

    @task
    def main_log(self, *text):
        debug(*text)

    @task
    def main_reload(self, sender=None, nick=None):
        before = time.time()

        self.processes["events"].stop(finish=True)
        self.processes["messages"].stop(finish=True)

        with self.safe.lock:
            debug("Reloading...")
            success = self.reload(sender, nick)
            if success:
                self.setup()
            debug("Reloaded")

        self.processes["messages"].action(process_messages, self.safe)
        self.processes["events"].action(process_events, self.safe)

        self.processes["messages"].start()
        self.processes["events"].start()

        duration = time.time() - before

        if sender and nick:
            if success:
                msg = "Completed the reload. Took %s seconds"
            else:
                msg = "The reload failed. Took %s seconds"
            msg = msg % round(duration, 3)
            self.safe.send_message("PRIVMSG", sender, nick + ": " + msg)

    @task
    def main_restart(self):
        # @@ Send QUIT
        self.processes.stop()
        debug("Stopped processes...")
        debug(" ")

        self.processes.empty()
        if not self.safe.options["flood"]:
            time.sleep(3)

        elapsed = 0
        while self.safe.commands.collectable(0):
            time.sleep(1)
            elapsed += 1
            if elapsed > 6:
                collected = self.safe.commands.collect(0)
                debug("Restart collected", collected, "commands")

                # Wait for the processes to exit
                # Otherwise, they might add to the queues after .empty()
                time.sleep(3)
                self.processes.empty()

        debug("Starting processes...")
        self.processes.start()

    # @@
    # @task
    def main_reconnect(self):
        self.processes["receive"].stop(finish=True)
        self.processes["send"].stop(finish=True)
        debug("Disconnected")
        debug("")

        if not self.safe.options["flood"]:
            time.sleep(6)

        self.processes.empty()

        debug("Reconnecting...")
        self.processes["receive"].action(process_receive, self.safe)
        self.processes["send"].action(process_send, self.safe)

        self.processes["receive"].start()
        self.processes["send"].start()

    @task
    def main_quit(self, nick=None):
        if nick is not None:
            self.safe.send_message("QUIT", "%s made me do it" % nick)
        else:
            self.safe.send_message("QUIT")

        self.processes.stop()
        sys.exit(0)

    @task
    def main_processes(self, sender=None, nick=None):
        process_names = []

        for p in multiprocessing.active_children():
            process_names.append(p.name)

        if sender and nick:
            number = len(process_names)
            names = ", ".join(sorted(process_names))
            msg = "%s processes are running (%s)" % (number, names)
            self.safe.send_message("PRIVMSG", sender, nick + ": " + msg)

    @task
    def main_collect(self, timeout=60):
        collectable = self.safe.commands.collectable(timeout)

        if collectable:
            debug("Pausing processes")
            self.processes.pause()

            debug("Collecting commands")
            collected = self.safe.commands.collect(max(0, timeout - 10))
            debug("Collected", collected, "commands")

            debug("Flushing queues")
            # self.processes.flush()

            debug("Setting new queues")
            self.safe.sending = self.processes["send"].queue
            self.safe.schedule = self.processes["schedule"].queue

            debug("Setting new actions")
            self.processes["send"].action(process_send, self.safe)
            self.processes["schedule"].action(process_schedule, self.safe)

            debug("Resuming...")
            self.processes.resume()
            debug("Resumed")

    @task
    def main_ping(self):
        self.safe.send_message("PING", self.safe.options["nick"])

    @task
    def main_ponged(self, pinged):
        ponged = self.safe.data.get("ponged", 0)
        if ponged < pinged:
            self.main.restart()

    @task
    def main_msg(self, recipient, text):
        self.safe.send_message("PRIVMSG", recipient, text)

### Processes ###

# (a) process:receive
def process_receive(safe):
    debug("START! process_receive")
    import ssl

    def receive_loop(safe, sockfile):
        count = 0
        for octets in sockfile:
            o = api.irc.parse_message(octets=octets)
            count += 1
            o.count = count
            safe.messages.put(o())

            # @@ debug here can hang if there are pipe problems
            debug("RECV:", octets)

    with safe.socket.makefile("rb") as sockfile:
        try: receive_loop(safe, sockfile)
        except (IOError, EOFError, socket.error, ssl.SSLError):
            # @@ debug here can hang if there are pipe problems
            debug("Got socket or SSL error")
            safe.tasks.put(("restart",))
        else:
            # @@ debug here can hang if there are pipe problems
            debug("Got regular disco")
            safe.tasks.put(("restart",)) # @@

    # @@ debug here can hang if there are pipe problems
    debug("DONE! process:receive")

# (b) process:send
def process_send(safe):
    import ssl

    debug("START! process_send")

    def send_loop():
        sent = 0

        with safe.socket.makefile("wb") as sockfile:
            while True:
                octets = safe.sending.get()
                if octets == "StopIteration":
                    break
    
                octets = octets.replace(b"\r", b"")
                octets = octets.replace(b"\n", b"")

                if len(octets) > 510:
                    octets = octets[:510]

                # @@ If we wait for QUIT, the socket can I/O error
                # This is strange because the receive socket is fine
                if not octets.startswith(b"QUIT"):
                    if not safe.options["flood"]:
                        now = time.time()
                        if sent > (now - 1):
                            time.sleep(0.5)
                        sent = now

                sockfile.write(octets + b"\r\n")
                sockfile.flush()

                # @@ debug here can hang if there are pipe problems
                debug("SENT:", octets + b"\r\n")
                safe.sending.task_done()

    try: send_loop()
    except (IOError, EOFError, socket.error, ssl.SSLError) as err:
        debug("Send Error:", err.__class__.__name__, err)
        ...

    safe.sending.task_done()
    # @@ debug here can hang if there are pipe problems
    debug("DONE! process:send")

# (c) process:messages
def process_messages(safe):
    debug("START! process_messages")
    safe.database.cache.usage = safe.database.load("usage") or {}
    while True:
        # debug("Waiting for message")
        message = safe.messages.get()
        # debug("Got message", message)
        if message == "StopIteration":
            break

        if message["command"] == "PRIVMSG":
            handle_named(safe, safe.named, message)
        safe.event_messages.put(message)
        safe.messages.task_done()

    safe.messages.task_done()
    # @@ debug here can hang if there are pipe problems
    debug("DONE! process:messages")

# (d) process:events
def process_events(safe):
    debug("START! process_events")
    while True:
        message = safe.event_messages.get()
        if message == "StopIteration":
            break

        commands = ["*", message["command"]]
        if message["count"] == 1:
            commands = ["1st"] + commands

        env = create_irc_env(safe, message)
        for priority in ["high", "medium", "low"]:
            for command in commands:
                for function in safe.events[priority].get(command, []):
                    def process_command(env):
                        try: function(env)
                        except Exception as err:
                            debug("Error:", str(err))

                    if not hasattr(function, "concurrent"):
                        process_command(env)
                    elif function.concurrent:
                        safe.commands.spawn(process_command, env)
                    else:
                        process_command(env)

        safe.event_messages.task_done()
    safe.event_messages.task_done()
    # @@ debug here can hang if there are pipe problems
    debug("DONE! process:events")

# (e) process:schedule
def process_schedule(safe):
    debug("START! process_schedule")

    import heapq
    import queue
    import time

    database = safe.database
    # @@ safe.queue is not reliable!
    receive = safe.schedule.get
    task = safe.tasks.put

    duration = 1/3
    # @@ init won't work here, doesn't return anything
    # could do an init and then a load...
    schedule = database.load("schedule") or []
    heapq.heapify(schedule)

    def periodic(period):
        def decorate(function):
            name = function.__name__

            periodic.functions[name] = function
            periodic.period[name] = period
            periodic.called[name] = 0
            periodic.stamp[name] = time.time()

            return function
        return decorate
    periodic.functions = {}
    periodic.period = {}
    periodic.called = {}
    periodic.stamp = {}

    # @periodic(safe.opt.time_between_pings_in_seconds)
    @periodic(300)
    def ping(current):
        task(("ping",))
        periodic.period["ponged"] = 60

    @periodic(None)
    def ponged(current):
        if periodic.called.get("ping"):
            pinged = periodic.stamp["ping"]

            # @@ periodic.period["ponged"] - 10?
            if current > (pinged + 50):
                task(("ponged", pinged))
                periodic.period["ponged"] = None

    # time_between_schedule_database_dumps
    # irc.process.schedule.periodic.dump.period.seconds
    @periodic(180)
    def dump(current):
        # @@ dump only if it's changed
        database.dump("schedule", schedule)

    @periodic(30)
    def collect(current):
        # @@ this means processes can run for about 90 seconds
        task(("collect",))

    def tick():
        nonlocal receive
        nonlocal schedule

        def elapsed():
            return time.time() - elapsed.start
        elapsed.start = time.time()

        # Spend 2/3 the duration handling the queue
        while True:
            remaining = (2/3 * duration) - elapsed()
            if remaining <= 0:
                break

            try: event = receive(timeout=remaining)
            except queue.Empty:
                break
            else:
                if event == "StopIteration":
                    return False

                if not isinstance(event, tuple):
                    debug("Not a tuple:", event)
                    continue
                if len(event) < 2:
                    continue
                if not (isinstance(event[0], int) or isinstance(event[0], float)):
                    continue

                if event[0] < elapsed.start:
                    # @@ dump
                    # @@ if event[1] == "stop", then quit
                    task(tuple(event[1:]))
                else:
                    heapq.heappush(schedule, event)

        # Handle the schedule
        current = time.time()

        while True:
            if not schedule:
                break

            event = heapq.heappop(schedule)
            if event[0] > current:
                heapq.heappush(schedule, event)
                break

            # @@ dump
            # @@ if event[1] == "stop", then quit
            task(tuple(event[1:]))

        # Handle periodic functions
        current = time.time()

        for name in periodic.functions:
            period = periodic.period[name]
            if not period:
                continue
            stamp = periodic.stamp[name]

            if current >= (stamp + period):
                debug("PERIODIC:", name)
                periodic.functions[name](current)
                periodic.called[name] += 1
                periodic.stamp[name] = time.time()

        # Sleep for the rest of the duration
        remaining = duration - elapsed()
        if remaining > 0:
            time.sleep(remaining)

        return True

    while tick():
        ...

    database.dump("schedule", schedule)

    # @@ debug here can hang if there are pipe problems
    debug("DONE! process:schedule")

### Process anciliaries ###

# used by process:messages
def handle_named(safe, named, message):
    env = create_irc_env(safe, message)

    if "command" in env:
        if env.command in named:
            def used(cmd):
                with safe.database.context("usage") as usage:
                    usage.setdefault(cmd, 0)
                    usage[cmd] += 1

            def process_command(env):
                # @@ multiprocessing.managers.RemoteError
                # env = create_irc_env(safe, message) # @@!
                # @@ pre-command
                try: named[env.command](env)
                except api.Error as err:
                    env.say("Error: %s" % err)
                except Exception as err:
                    import os.path
                    import traceback

                    name = err.__class__.__name__
                    stack = traceback.extract_tb(err.__traceback__, limit=2)
                    item = list(stack.pop())
                    item[0] = os.path.basename(item[0])
                    where = "%s:%s at %s(...) %s" % tuple(item)
                    env.say("Script Error: %s: %s, in %s" % (name, err, where))

                    debug("---")
                    for line in traceback.format_exception(
                            err.__class__, err, err.__traceback__):
                        line = line.rstrip("\n")
                        line = line.replace(duxlot.path + os.sep, "")
                        debug(line)
                    debug("---")
                # @@ post-command
                used(env.command)

            safe.commands.spawn(process_command, env)
    debug("Quitting handle_named")

def create_irc_env(safe, message):
    env = duxlot.Storage()

    env.message = message
    env.event = message["command"]
    if "prefix" in message:
        env.nick = message["prefix"]["nick"]

    if env.event == "PRIVMSG":
        env.sender = message["parameters"][0]
        env.text = message["parameters"][1]
        if "address" in safe.data:
            env.limit = 498 - len(env.sender) + len(safe.data["address"])

        prefixes = safe.options["prefixes"]
        if env.sender in prefixes:
            prefix = prefixes[env.sender]
        else:
            prefix = safe.options["prefix"]

        if env.text.startswith(prefix):
            env.prefix = prefix
            sans_prefix = env.text[len(prefix):]

            if " " in sans_prefix:
                env.command, env.arg = sans_prefix.split(" ", 1)
            else:
                env.command, env.arg = sans_prefix, ""

        env.private = env.sender == safe.options["nick"]
        if env.private:
            env.sender = env.nick

    env.data = safe.data
    env.options = safe.options
    env.lock = safe.lock
    # @@ schedule wrapper?
    # env.task = safe.tasks.put
    env.database = safe.database
    env.schedule = safe.schedule.put
    env.sent = safe.sending.join
    env.log = safe.log

    if "sender" in env:
        def say(text):
            safe.send_message("PRIVMSG", env.sender, text)
        env.say = say

    if ("nick" in env) and ("sender" in env):
        def reply(text):
            text = env.nick + ": " + text
            safe.send_message("PRIVMSG", env.sender, text)
        env.reply = reply

    def send(*arguments):
        safe.send_message(*arguments)
    env.send = send

    def msg(recipient, text):
        safe.send_message("PRIVMSG", recipient, text)
    env.msg = msg

    # @@ this shouldn't really be here...
    for builder in duxlot.builders:
        env = builder(env)

    return env

# process-safe
def create_send_message(sending, log):
    def send_message(*arguments):
        arguments = list(arguments)

        if not all (isinstance(arg, str) for arg in arguments):
            log("Error: send_message: %s" % arguments)
            return

        if len(arguments) > 1: # and " " in arguments[-1]
            arguments[-1] = ":" + arguments[-1]

        sending.put(" ".join(arguments).encode("utf-8", "replace"))
    return send_message

# @@ a more efficient message parser
# @@ a more efficient environment builder
# @@ a naïve timer for other commands
# @@ separate namespace for command chaining state
# @@ note where the lock is used, and the types of usage
# @@ ..commands for web services, or .regular and .services other
# @@ last n seconds of events, event list
# @@ reload config. nick/channels/prefix might change, etc.
# @@ make F008 work, and the character itself
# @@ make it clear when a child process goes boom
# @@ ignore list
# @@ show/delete my messages
# @@ find out the flood limits
# @@ recovering from process errors
# @@ make tasks queue joinable
# @@ latest version warning
# @@ travis build
# @@ ./release or ./tag?
# @@ cache for channel users
# @@ namespaced data, and item style putting
# @@ relative Location bug
# @@ better config documentation
# @@ credentialise admin.py
# @@ bot / task and schedule functions for commands to use
# @@ writebackable config
# @@ refuse to run in .duxlot-src
# @@ reply should automatically not prepend nick in private
