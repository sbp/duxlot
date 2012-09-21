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
    from . import options
    from . import process
else:
    import api
    import options
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

        self.manager = multiprocessing.Manager()
        self.lock = multiprocessing.RLock()
        self.processes = process.Processes(self.create_socket)
        self.commands = process.Commands(self.manager)

        self.private = self.create_private()
        self.public = self.create_public()

        self.standard_directory = os.path.join(duxlot.path, "standard")
        self.populate_options()
        self.handle_signals()

        self.load()
        self.setup()

        self.start()
        self.tasks()

    def check_semaphores(self):
        try: multiprocessing.Semaphore()
        except OSError as err:
            debug("Oh dear, your system might not allow POSIX Semaphores")
            debug("See http://stackoverflow.com/questions/2009278 to fix")
            sys.exit(1)

    def create_private(self):
        private = duxlot.Storage()

        private.command = self.commands.spawn
        # private.events is set later on
        # private.named is set later on
        private.queue = {
            "main": self.processes.queue,
            "send": self.processes["send"].queue,
            "messages": self.processes["messages"].queue,
            "events": self.processes["events"].queue,
            "schedule": self.processes["schedule"].queue
        }
        # private.socket is set in process.Process

        return private

    def create_public(self):
        public = duxlot.Storage()

        public.data = self.manager.dict()
        public.data.stamp = 0
        public.database = duxlot.database(
            duxlot.config.path(self.config.base + ".database"),
            self.manager.Namespace()
        )
        public.debug = debug
        public.options = options.Options(
            self.config.name,
            self.manager,
            public
        )

        def schedule(*args):
            self.private.queue["schedule"].put(args)
        public.schedule = schedule

        def task(*args):
            self.private.queue["schedule"].put((0,) + args)
        public.task = task

        def send(*args):
            if not all (isinstance(arg, str) for arg in args):
                debug("Error: public.send:", args)
                return
    
            if len(args) > 1:
                args = list(args)
                args[-1] = ":" + args[-1]
    
            octets = " ".join(args).encode("utf-8", "replace")
            self.processes["send"].queue.put(octets)
        public.send = send

        def msg(*args):
            send("PRIVMSG", *args)
        public.msg = msg

        return public

    def populate_options(self):
        group = self.public.options.group
        option = self.public.options.option
        
        @group()
        class address(option):
            "Address of the server to connect to"
            default = "irc.freenode.net:6667"
        
            def parse(self, value):
                match = self.regexp(r"(ssl )?([^:]+)(?:[:]([0-9]+))?", value)
                ssl, host, port = match.groups()
                return {
                    "ssl": True if ssl else False,
                    "host": host,
                    "port": int(port) if port else 6667
                }

        @group()
        class flood(option):
            "Whether to flood or not"
            default = False
            types = {bool}
        
        @group()
        class nick(option):
            "Nick of the bot"
            @property
            def default(self):
                import random
                # 000 to 999 inclusive
                return "duxlot%03i" % random.randrange(1000)
        
            def parse(self, value):
                # RFC 2812 put the length limit at 9 characters
                # Then it says servers ought to accept larger nicknames...
                # Setting the limit to 32 here as a sanity check
                # Note that some nicknames in the wild start with numbers
                prefix = r"[A-Za-z0-9\x5B-\x60\x7B-\x7D]"
                extra = r"[A-Za-z0-9\x5B-\x60\x7B-\x7D-]"
                self.regexp(r"(%s%s{,31})" % (prefix, extra), value)
        
            # @@ reactions could be in the code setting the option...
            def react(self):
                self.public.send("NICK", self.data.value)
        
        @group()
        class modules(option):
            "Modules to load"
            default = [self.standard_directory]
            types = {list}
        
            def parse(self, value):
                ...
        
            def react(self):
                self.public.task("reload")
        
        @group()
        class prefix(option):
            "Default command prefix, or channel to prefix mapping"
            default = "."
            types = {dict, str}
        
            def parse(self, value):
                def check(prefix):
                    if len(prefix) > 128:
                        # 64 is just long enough to allow the supercombiner
                        raise ValueError("Maximum prefix length is 64 characters")
                    
                if isinstance(value, str):
                    check(value)
                    return {"channels": {"": value}}

                for prefix in value.values():
                    check(prefix)
                return {"channels": value}
        
        self.public.options.complete()

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
            self.public.send("QUIT", message)

            # This calls .finish(), so the QUIT above should work
            self.processes.stop()

            # Stop any stray commands, potentially corrupting queues
            try: self.commands.collect(0)
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

    def load(self, react=False):
        import importlib

        self.public.options.load(react=react, validate=False)

        def info(identifier):
            if os.path.isdir(identifier):
                for name in modules_in_directory(identifier):
                    yield identifier, name
            else:
                yield os.path.split(identifier)

        include = []
        exclude = set()
        standard = {"admin", "core", "services", "start", "text"}

        identifiers = self.public.options("modules")
        for identifier in identifiers:
            if identifier.startswith("-"):
                if os.path.isdir(identifier):
                    continue # @@ Could remove this restriction
                for directory, name in info(identifier):
                    exclude.add((directory, name))
            else:
                for directory, name in info(identifier):
                    include.append((directory, name))

        self.modules = {}
        module_info = []

        for directory, name in include:
            if name in sys.modules:
                debug("Warning: Skipping duplicate: %s" % module_name)
                continue

            if (directory, name) in exclude:
                continue

            if directory == self.standard_directory:
                if not (name in standard):
                    # @@ User error message
                    raise ValueError(name, "is not a standard module")

            # @@ Only make duxlot.path available to standard_directory
            # Make duxlot.py available to all though?
            sys.path[:0] = [directory, duxlot.path]
            module = importlib.import_module(name)
            self.modules[(directory, name)] = module
            sys.path[:2] = []

            if directory == self.standard_directory:
                udir = "standard"
            else:
                udir = duxlot.config.reduceuser(directory)
            debug(name, "imported from", udir)
            module_info.append((udir, name))

        self.public.data.modules = module_info

    def reload(self, sender=None, nick=None):
        import imp

        def error(msg):
            if sender and nick:
                self.public.msg(sender, nick + ": " + msg)

        duxlot.clear()

        sys.path[:0] = [duxlot.path]
        imp.reload(api)
        sys.path[:1] = []

        for (directory, module_name), module in self.modules.items():
            sys.path[:0] = [directory, duxlot.path]

            try: reloaded = imp.reload(module)
            except Exception as err:
                message = "%s: %s" % (err.__class__.__name__, err)
                debug(message)
                error(message)

                return False
            else:
                self.modules[(directory, module_name)] = reloaded
            finally:
                sys.path[:2] = []

        return True

    def setup(self, react=False):
        # @@ Recording sources of commands
        for startup in duxlot.startups:
            startup(self.public)

        self.private.named = duxlot.commands.copy()
        self.private.events = duxlot.events.copy()

        self.public.options.load(react=react)

    def start(self):
        functions = {
            "receive": process_receive,
            "send": process_send,
            "messages": process_messages,
            "events": process_events,
            "schedule": process_schedule
        }

        for name, function in functions.items():
            self.processes[name].action(function, self.private, self.public)
        self.processes.start()

    def create_socket(self):
        sock = socket.socket(socket.AF_INET, socket.TCP_NODELAY)

        if self.public.options("address", "ssl") is True:
            import ssl
            debug("Warning: Using SSL, but not validating the cert!")
            sock = ssl.wrap_socket(
                sock,
                server_side=False,
                cert_reqs=ssl.CERT_NONE # @@ or CERT_REQUIRED
            )

        address = (
            self.public.options("address", "host"),
            self.public.options("address", "port")
        )

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
            parameters = self.private.queue["main"].get()
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

        with self.lock:
            debug("Reloading...")
            success = self.reload(sender, nick)
            if success:
                self.setup(react=True)
            debug("Reloaded")

        self.processes["messages"].action(
            process_messages, self.private, self.public
        )
        self.processes["events"].action(
            process_events, self.private, self.public
        )

        self.processes["messages"].start()
        self.processes["events"].start()

        duration = time.time() - before

        if sender and nick:
            if success:
                msg = "Completed the reload. Took %s seconds"
            else:
                msg = "The reload failed. Took %s seconds"
            msg = msg % round(duration, 3)
            self.public.msg(sender, nick + ": " + msg)

    @task
    def main_restart(self):
        # @@ Send QUIT
        self.processes.stop()
        debug("Stopped processes...")
        debug(" ")

        self.processes.empty()
        if not self.public.options("flood"):
            time.sleep(3)

        elapsed = 0
        while self.commands.collectable(0):
            time.sleep(1)
            elapsed += 1
            if elapsed > 6:
                # commands.collect waits for the processes to exit
                collected = self.commands.collect(0)
                debug("Restart collected", collected, "commands")

                # Should be safe to do this without delay
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

        if not self.public.options("flood"):
            time.sleep(6)

        self.processes.empty()

        debug("Reconnecting...")
        self.processes["receive"].action(
            process_receive, self.private, self.public
        )
        self.processes["send"].action(
            process_send, self.private, self.public
        )

        self.processes["receive"].start()
        self.processes["send"].start()

    @task
    def main_quit(self, nick=None):
        if nick is not None:
            self.public.send("QUIT", "%s made me do it" % nick)
        else:
            self.public.send("QUIT")

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
            self.public.msg(sender, nick + ": " + msg)

    @task
    def main_pids(self, sender, nick):
        if sender and nick:
            pids = ["receive: %s" % self.processes["receive"].process.pid]
            for name in self.processes.queues:
                pid = self.processes[name].process.pid
                pids.append("%s: %s" % (name, pid))
            text = ", ".join(pids)
            self.public.msg(sender, nick + ": " + text)

    @task
    def main_collect(self, timeout=60):
        collectable = self.commands.collectable(timeout)

        if collectable:
            debug("Pausing processes")
            # @@ Finish sending, join the sending queue
            self.private.queue["send"].join()
            self.processes.empty()
            self.processes.pause()

            debug("Collecting commands")
            collected = self.commands.collect(max(0, timeout - 10))
            debug("Collected", collected, "commands")

            debug("Flushing queues")
            # self.processes.flush()

            # @@ But we don't reset them!
            # debug("Setting new queues")
            # self.processes["send"].queue = multiprocessing.JoinableQueue()
            # self.processes["schedule"].queue = multiprocessing.JoinableQueue()
            # self.p... oh

            debug("Setting new actions")
            self.processes["send"].action(
                process_send, self.private, self.public
            )
            self.processes["schedule"].action(
                process_schedule, self.private, self.public
            )

            debug("Resuming...")
            self.processes.resume()
            debug("Resumed")

    @task
    def main_ping(self):
        self.public.send("PING", self.public.options("nick"))

    @task
    def main_ponged(self, pinged):
        ponged = self.public.data.get("ponged", 0)
        if ponged < pinged:
            self.main.restart()

    @task
    def main_msg(self, recipient, text):
        self.public.msg(recipient, text)

### Processes ###

# (a) process:receive
def process_receive(private, public):
    debug("START! process_receive")
    import ssl

    def receive_loop(sockfile, private):
        count = 0
        for octets in sockfile:
            o = api.irc.parse_message(octets=octets)
            count += 1
            o.count = count
            private.queue["messages"].put(o())

            # @@ debug here can hang if there are pipe problems
            debug("RECV:", octets)

    with private.socket.makefile("rb") as sockfile:
        try: receive_loop(sockfile, private)
        except (IOError, EOFError, socket.error, ssl.SSLError):
            # @@ debug here can hang if there are pipe problems
            debug("Got socket or SSL error")
            public.task("restart")
        else:
            # @@ debug here can hang if there are pipe problems
            debug("Got regular disco")
            public.task("restart") # @@

    # @@ debug here can hang if there are pipe problems
    debug("DONE! process:receive")

# (b) process:send
def process_send(private, public):
    import ssl

    debug("START! process_send")

    send_get = private.queue["send"].get
    send_done = private.queue["send"].task_done

    def send_loop():
        sent = 0
        
        with private.socket.makefile("wb") as sockfile:
            while True:
                octets = send_get()
                if octets == "StopIteration":
                    break
    
                octets = octets.replace(b"\r", b"")
                octets = octets.replace(b"\n", b"")

                if len(octets) > 510:
                    octets = octets[:510]

                # @@ If we wait for QUIT, the socket can I/O error
                # This is strange because the receive socket is fine
                if not octets.startswith(b"QUIT"):
                    if not public.options("flood"):
                        now = time.time()
                        if sent > (now - 1):
                            time.sleep(0.5)
                        sent = now

                sockfile.write(octets + b"\r\n")
                sockfile.flush()

                # @@ debug here can hang if there are pipe problems
                debug("SENT:", octets + b"\r\n")
                send_done()

    try: send_loop()
    except (IOError, EOFError, socket.error, ssl.SSLError) as err:
        debug("Send Error:", err.__class__.__name__, err)

    send_done()
    # @@ debug here can hang if there are pipe problems
    debug("DONE! process:send")

# (c) process:messages
def process_messages(private, public):
    debug("START! process_messages")
    public.database.cache.usage = public.database.load("usage") or {}
    messages_get = private.queue["messages"].get
    while True:
        # debug("Waiting for message")
        message = messages_get()
        stamp = time.time()
        # debug("Got message", message)
        if message == "StopIteration":
            break

        if message["command"] == "PRIVMSG":
            env = create_irc_env(public, message)

            if "command" in env:
                if env.command in private.named:
                    def process_command(env):
                        # @@ pre-command
                        try: private.named[env.command](env)
                        except api.Error as err:
                            env.say("Error: %s" % err)
                        except Exception as err:
                            import os.path
                            import traceback
        
                            name = err.__class__.__name__
                            tb = err.__traceback__
                            stack = traceback.extract_tb(tb, limit=2)
                            item = list(stack.pop())
                            item[0] = os.path.basename(item[0])
                            where = "%s:%s at %s(...) %s" % tuple(item)
                            msg = "Script Error: %s: %s, in %s"
                            env.say(msg % (name, err, where))
        
                            debug("---")
                            for line in traceback.format_exception(
                                    err.__class__, err, err.__traceback__):
                                line = line.rstrip("\n")
                                line = line.replace(duxlot.path + os.sep, "")
                                debug(line)
                            debug("---")
                        # @@ post-command
        
                        with public.database.context("usage") as usage:
                            usage.setdefault(env.command, 0)
                            usage[env.command] += 1
        
                    private.command(process_command, env)

        private.queue["events"].put(message)
        private.queue["messages"].task_done()

    private.queue["messages"].task_done()
    # @@ debug here can hang if there are pipe problems
    debug("DONE! process:messages")

# (d) process:events
def process_events(private, public):
    debug("START! process_events")
    while True:
        message = private.queue["events"].get()
        if message == "StopIteration":
            break

        commands = ["*", message["command"]]
        if message["count"] == 1:
            commands = ["1st"] + commands

        env = create_irc_env(public, message)
        for priority in ["high", "medium", "low"]:
            for command in commands:
                for function in private.events[priority].get(command, []):
                    def process_command(env):
                        try: function(env)
                        except Exception as err:
                            debug("Error:", str(err))

                    if not hasattr(function, "concurrent"):
                        process_command(env)
                    elif function.concurrent:
                        private.command(process_command, env)
                    else:
                        process_command(env)

        private.queue["events"].task_done()
    private.queue["events"].task_done()
    # @@ debug here can hang if there are pipe problems
    debug("DONE! process:events")

# (e) process:schedule
def process_schedule(private, public):
    debug("START! process_schedule")

    import heapq
    import queue
    import time

    database = public.database
    # @@ the set queue is not reliable!
    receive = private.queue["schedule"].get
    task = private.queue["main"].put

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

    # @periodic(public.options("time_between_pings_in_seconds"))
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

def create_irc_env(public, message):
    proto = public()
    env = duxlot.Storage(proto.copy())

    env.message = message
    env.event = message["command"]

    if "prefix" in message:
        env.nick = message["prefix"]["nick"]

    if env.event == "PRIVMSG":
        env.sender = message["parameters"][0]
        env.text = message["parameters"][1]
        if "address" in public.data:
            env.limit = 498 - len(env.sender + public.data["address"])

        prefix = public.options("prefix", "channels").get(env.sender)
        if prefix is None:
            prefix = public.options("prefix", "channels").get("", ".") # @@
        env.prefix = prefix

        if env.text.startswith(prefix):            
            sans_prefix = env.text[len(prefix):]

            if " " in sans_prefix:
                env.command, env.arg = sans_prefix.split(" ", 1)
            else:
                env.command, env.arg = sans_prefix, ""

        env.private = env.sender == public.options("nick")
        if env.private:
            env.sender = env.nick

    if "sender" in env:
        def say(text):
            public.msg(env.sender, text)
        env.say = say

    if ("nick" in env) and ("sender" in env):
        def reply(text):
            public.msg(env.sender, env.nick + ": " + text)
        env.reply = reply

    # @@ this shouldn't really be here...
    for builder in duxlot.builders:
        env = builder(env)

    return env

# @@ a more efficient message parser
# @@ a more efficient environment builder
# @@ a naïve timer for other commands
# @@ separate namespace for command chaining state
# @@ ..commands for web services, or .regular and .services other
# @@ last n seconds of events, event list
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
# @@ refuse to run in .duxlot-src
# @@ reply should automatically not prepend nick in private
