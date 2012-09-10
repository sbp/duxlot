#!/usr/bin/env python3
# @@ -Ou

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
else:
    import api

def modules_in_directory(directory):
    import glob
    names = []
    for name in glob.glob(os.path.join(directory, "*.py")):
        name = os.path.basename(name)
        names.append(name[:-3])
    return names

# @@ a more efficient message parser
# @@ a more efficient environment builder
# @@ a naïve timer for other commands
# @@ separate namespace for command chaining state
# @@ note where the lock is used, and the types of usage
# @@ periodic scheduling
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

class Client(object):
    def __init__(self, options_filename, options_base, options_data):
        try: sending = multiprocessing.JoinableQueue()
        except OSError as err:
            print("Oh dear, your system might not allow POSIX Semaphores")
            print("See http://stackoverflow.com/questions/2009278 to fix")
            __import__("sys").exit(1)

        manager = multiprocessing.Manager()
        lock = multiprocessing.RLock()

        self.options_filename = options_filename
        self.base = options_base
        db_base = options_data["database"]
        db_base = db_base.replace("$(BASE)", self.base)
        db_base = duxlot.config.path(db_base)

        # messages: received -> messages
        # sending: * -> send
        # event_messages: messages -> events

        # tasks: * -> main
        # schedule: * -> schedule

        tasks = multiprocessing.Queue()

        def log(*text):
            tasks.put(("log",) + text)

        # perhaps split into primitive stuff and user friendly stuff
        # private_safe, and public_safe
        self.safe = duxlot.FrozenStorage({
            "messages": multiprocessing.JoinableQueue(),
            "sending": sending,
            "event_messages": multiprocessing.JoinableQueue(),
            "schedule": multiprocessing.JoinableQueue(),
            "tasks": tasks,
            "manager": manager,
            "data": manager.dict(),
            "lock": lock,
            "options": manager.dict(options_data),
            "send_message": create_send_message(sending, self.perform_log),
            "database": create_database_interface(db_base, manager),
            "log": log
        })

        def terminate(signum, frame):
            # print(frame)
            self.safe.send_message("QUIT", "? made me do it") # @@
            self.perform_quit()
        signal.signal(signal.SIGTERM, terminate)
        signal.signal(signal.SIGINT, terminate)

        self.inactive = {
            "process:schedule": multiprocessing.Event(),
            "process:events": multiprocessing.Event(),
            "process:messages": multiprocessing.Event(),
            "process:send": multiprocessing.Event()
        }

        self.queue_processes = {
            "process:schedule": self.safe.schedule,
            "process:events": self.safe.event_messages,
            "process:messages": self.safe.messages,
            "process:send": self.safe.sending
        }

        self.all_process_names = (
            "process:command",
            "process:schedule",
            "process:events",
            "process:messages",
            "process:send",
            "process:receive"
        )

        self.queue_process_names = self.all_process_names[1:-1]

        self.standard_directory = os.path.join(duxlot.path, "standard")

        self.import_modules()
        self.setup_commands()

        self.create_socket()
        self.start_processes()
        self.handle_perform_loop()

    def handle_perform_loop(self):
        handlers = {
            "quit": self.perform_quit,
            "reload": self.perform_reload,
            "restart": self.perform_restart,
            "processes": self.perform_processes,
            "log": self.perform_log
        }

        while True:
            task = self.safe.tasks.get()
            task_name, arguments = task[0], task[1:]

            if task_name in handlers:
                try: handlers[task_name](*arguments)
                except Exception as err:
                    self.perform_log("Task Error: %s" % err)

    def import_modules(self):
        import importlib

        self.modules = {}

        standard = set(self.safe.options["standard"])
        directories = [self.standard_directory] + self.safe.options["user"]

        for directory in directories:
            module_names = modules_in_directory(directory)

            if directory == self.standard_directory:
                if standard != {"*"}:
                    module_names = standard & set(module_names)

            for module_name in module_names:
                identifier = (module_name, directory)

                sys.path[:0] = [directory, duxlot.path]
                self.modules[identifier] = importlib.import_module(module_name)
                print("Imported", module_name, "from", directory)
                sys.path[:2] = []

    def reload_modules(self, sender=None, nick=None):
        import imp

        def error(msg):
            if sender and nick:
                self.safe.send_message("PRIVMSG", sender, nick + ": " + msg)

        duxlot.clear()

        for (module_name, directory), module in self.modules.items():
            sys.path[:0] = [directory, duxlot.path]

            try: reloaded = imp.reload(module)
            except Exception as err:
                message = "%s: %s" % (err.__class__.__name__, err)
                self.perform_log(message)
                error(message)

                return False
            else:
                self.modules[(module_name, directory)] = reloaded
            finally:
                sys.path[:2] = []

        return True

    def do_actual_reload(self, sender=None, nick=None):
        with self.safe.lock:
            self.perform_log("Reloading...")
            # backup = duxlot.backup()
            success = self.reload_modules(sender, nick)
            if success:
                self.setup_commands()
            # else:
            #     duxlot.restore(backup)
            self.perform_log("Reloaded")

    def perform_reload(self, sender=None, nick=None):
        self.complete_queue_processes()

        self.do_actual_reload(sender, nick)

        self.start_queue_processes()
        if sender and nick:
            self.safe.send_message("PRIVMSG", sender, nick + ": Reload complete")

    def perform_restart(self):
        try: self.socket.shutdown(socket.SHUT_RDWR)
        except socket.error:
            ...
        # self.socket.detach()
        self.complete_queue_processes()
        if not self.processes_completed_cleanly():
            self.terminate_all_processes()

        self.do_actual_reload()

        self.create_socket()
        self.start_processes()

    def setup_commands(self):
        # @@ recording sources of commands
        self.named = duxlot.commands.copy()
        self.events = duxlot.events.copy()
        for startup in duxlot.startups:
            startup()

    def create_socket(self):
        self.socket = socket.socket(socket.AF_INET, socket.TCP_NODELAY)

        if self.safe.options["ssl"] is True:
            import ssl
    
            print("Warning: Using SSL, but not validating the cert!")
            self.socket = ssl.wrap_socket(
                self.socket,
                server_side=False,
                cert_reqs=ssl.CERT_NONE # @@ or CERT_REQUIRED
            )

        self.socket.connect((self.safe.options["server"], self.safe.options["port"]))

    def start_processes(self):
        # process:events could be pooled
        self.start_queue_processes()
        process(process_receive, (self.safe, self.socket.makefile))

    def start_queue_processes(self):
        process(process_schedule,
            (self.inactive["process:schedule"], self.safe))
        process(process_events,
            (self.inactive["process:events"], self.safe, self.events))
        process(process_messages,
            (self.inactive["process:messages"], self.safe, self.named))
        process(process_send,
            (self.inactive["process:send"], self.safe, self.socket.makefile))

    def perform_log(self, *text):
        with self.safe.lock:
            print(*text) # @@ or write to a file, etc.

    def active_processes(self, name=None):
        processes = {}
        for p in multiprocessing.active_children():
            if p in self.all_process_names:
                processes.setdefault(p.name, []).append(p)

        if name in processes:
            return processes[name]
        return processes

    def active_process(self, name):
        processes = self.active_processes()
        return name in processes

    def terminate_process(self, name, wait=None):
        processes = self.active_processes()
        if (name in processes) and (name in self.all_process_names):
            for process in processes[name]:
                self.perform_log("Sending SIGTERM to %s" % name)
                process.terminate()
                if wait:
                    time.sleep(wait)

    def terminate_all_processes(self):
        for process_name in self.all_process_names:
            self.terminate_process(process_name)

    # @@ wait / timeout
    def complete_processes(self, names, join=True):
        for name in names:
            if name in self.queue_process_names:
                queue = self.queue_processes[name]
                queue.put("StopIteration")
                self.perform_log("Send StopIteration to %s" % name)

            elif name == "process:receive":
                self.perform_log("Not implemented")

        for name in names:
            # @@ process:command instances won't have an event
            if (name in self.queue_processes) and join:
                event = self.inactive[name]
                self.perform_log("Waiting up to 5secs for %s to call inactive.set" % name)
                event.wait(timeout=5)

    def complete_queue_processes(self):
        self.complete_processes(self.queue_process_names)

    def processes_completed_cleanly(self, poll=0.2, timeout=2):
        start = time.time()
        while True:
            active = self.active_processes()
            if not active:
                break
            if time.time() > (start + timeout):
                for item in active.items():
                    self.perform_log("STILL RUNNING:", item)
                return False
            time.sleep(poll)
        return True

    def perform_quit(self):
        import sys
        # with self.safe.lock:
        self.complete_queue_processes()
        if not self.processes_completed_cleanly():
            self.terminate_all_processes()
        sys.exit(0)

    def perform_processes(self, sender=None, nick=None):
        process_names = []
        for p in multiprocessing.active_children():
            process_names.append(p.name)
        if sender and nick:
            number = len(process_names)
            names = ", ".join(sorted(process_names))
            msg = "%s processes are running (%s)" % (number, names)
            self.safe.send_message("PRIVMSG", sender, nick + ": " + msg)


### Processes ###

# (a) process:receive
def process_receive(safe, makefile):
    import ssl

    def receive(safe, sockfile):
        count = 0
        for octets in sockfile:
            o = api.irc.parse_message(octets=octets)
            count += 1
            o.count = count
            safe.messages.put(o())

            # @@ remove this?
            safe.log("RECV:", octets)

    with makefile("rb") as sockfile:
        try: receive(safe, sockfile)
        except (ssl.SSLError, socket.error):
            safe.tasks.put("restart")
        # except (IOError, EOFError):
        #     ...
    safe.log("DONE! process:receive")

# (b) process:send
def process_send(inactive, safe, makefile):
    inactive.clear()
    sent = 0
    with makefile("wb") as sockfile:
        while True:
            octets = safe.sending.get()
            if octets == "StopIteration":
                break

            octets = octets.replace(b"\r", b"")
            octets = octets.replace(b"\n", b"")

            now = time.time()
            if sent > (now - 1):
                time.sleep(0.5)
            sent = now

            if len(octets) > 510:
                octets = octets[:510]

            sockfile.write(octets + b"\r\n")
            sockfile.flush()

            # @@ remove this?
            safe.log("SENT:", octets + b"\r\n")
            safe.sending.task_done()
    safe.sending.task_done()
    safe.log("DONE! process:send")
    inactive.set()

# (c) process:messages
def process_messages(inactive, safe, named):
    inactive.clear()
    safe.database.cache.usage = safe.database.load("usage") or {}
    while True:
        message = safe.messages.get()
        if message == "StopIteration":
            break

        if message["command"] == "PRIVMSG":
            handle_named(safe, named, message)
        safe.event_messages.put(message)
        safe.messages.task_done()

    safe.messages.task_done()
    safe.log("DONE! process:messages")
    inactive.set()

# (d) process:events
def process_events(inactive, safe, events):
    inactive.clear()

    while True:
        message = safe.event_messages.get()
        if message == "StopIteration":
            break

        commands = ["*", message["command"]]
        if message["count"] == 1:
            commands = ["1st"] + commands

        for priority in ["high", "medium", "low"]:
            for command in commands:
                for function in events[priority].get(command, []):
                    def process_command():
                        # Must be inside, otherwise it may be GCed
                        env = create_irc_env(safe, message)
                        try: function(env)
                        except Exception as err:
                            safe.log("Error:", str(err))

                    if not hasattr(function, "concurrent"):
                        process_command()
                    else:
                        process(process_command, ())

        safe.event_messages.task_done()
    safe.event_messages.task_done()
    safe.log("DONE! process:events")
    inactive.set()

# (e) process:schedule
def process_schedule(inactive, safe):
    inactive.clear()

    import time
    import heapq
    import queue

    heap = safe.database.load("schedule") or []
    heapq.heapify(heap)

    safe.data["pinged"] = time.time()
    safe.data["ponged"] = safe.data["pinged"]

    # while tick():
    #    ...

    safe.data["biggest_time"] = 0
    safe.data["smallest_time"] = 100000
    average_time = 0

    while True:
        time_at_start = time.time()
        item = None
        changed = False
        while True:
            try: item = safe.schedule.get_nowait()
            except queue.Empty:
                break

            if item == "StopIteration":
                break

            if changed is False:
                changed = True
            heapq.heappush(heap, item)

        if item == "StopIteration":
            break

        if changed:
            safe.database.dump("schedule", heap)

        now = time.time()
        while True:
            if heap:
                t, recipient, nick, text = heapq.heappop(heap)
            else:
                break

            if t > now:
                heapq.heappush(heap, (t, recipient, nick, text))
                break
            else:
                if text:
                    safe.send_message("PRIVMSG", recipient, nick + ": " + text)
                else:
                    safe.send_message("PRIVMSG", recipient, nick + "!")
                safe.database.dump("schedule", heap)

        if now > (safe.data["pinged"] + 300):
            safe.send_message("PING", safe.options["nick"])
            safe.data["pinged"] = now

        if now > (safe.data["pinged"] + 60):
            if safe.data["ponged"] < (safe.data["pinged"] - 60):
                safe.tasks.put("restart")
                # break - would probably cause a dual process complete call
                # @@ only with task_done() though?

        # http://www.wolframalpha.com/input/?i=1%2F3+-+1%2F5
        time_taken = time.time() - time_at_start
        if time_taken > safe.data["biggest_time"]:
            safe.data["biggest_time"] = time_taken
        if time_taken < safe.data["smallest_time"]:
            safe.data["smallest_time"] = time_taken

        # 09:50 <sbp> ^time-taken
        # 09:50 <duxlott> Smallest: 0.0003108978271484375
        # 09:50 <duxlott> Biggest: 0.0021529197692871094

        tick_duration = 1/3
        min_sleep = 1/5
        delay = tick_duration - (time.time() - now)
        delay = min_sleep if (delay < min_sleep) else delay
        time.sleep(delay)
        # .1 - 0.25% cpu, .02 - 1% cpu, .01 - 2% cpu, .001 - 13% cpu
        if item:
            safe.schedule.task_done()
    safe.schedule.task_done()
    safe.log("DONE! process:schedule")
    inactive.set()


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

            def process_command():
                # @@ multiprocessing.managers.RemoteError
                env = create_irc_env(safe, message) # @@!
                # @@ pre-command
                if not safe.options["debug"]:
                    try: named[env.command](env)
                    # except duxlot.Error as err:
                    #     irc.say("API Error: %s" % err) # @@!
                    except Exception as err:
                        import os.path, traceback
                        item = list(traceback.extract_tb(err.__traceback__, limit=2).pop())
                        item[0] = os.path.basename(item[0])
                        where = "%s:%s %s(...) %s" % tuple(item)
                        irc.say("Python Error. %s: %s" % (err, where))
                else:
                    named[env.command](env)
                # @@ post-command
                used(env.command)

            # while number_of_processes >= process_limit:
            #    time.sleep(0.5)
            # if > timeout, complain

            process(process_command, tuple())
    safe.log("Quitting handle_named")

# used by create_input
def administrators(options):
    permitted = set()
    owner = options["owner"]
    if owner:
        permitted.add(owner)
    admins = options["admins"]
    if admins:
        set.update(admins)
    return permitted

def create_irc_env(safe, message):
    env = duxlot.Storage()

    env.message = message
    env.event = message["command"]
    if "prefix" in message:
        env.nick = message["prefix"]["nick"]

    if message["command"] == "PRIVMSG":
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

        # this should be in a separate admin augmentation
        # only to be added if the admin module is loaded
        env.owner = env.nick == safe.options["owner"]
        env.admin = env.nick in administrators(safe.options) # @@!
        env.adminchan = env.sender in safe.options["adminchans"]

        def credentials(person, place):
            person_okay = {
                "owner": env.owner,
                "admin": env.owner or env.admin
            #   "anyone": True # @@ for anyone + adminchan
            }.get(person, False)
    
            place_okay = {
                "anywhere": True,
                "adminchan": env.adminchan or env.private,
                "private": env.private
            }.get(place, False)

            return person_okay and place_okay
        env.credentials = credentials

    env.data = safe.data
    env.options = safe.options
    env.lock = safe.lock
    env.task = safe.tasks.put
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

def process(target, args):
    name = target.__name__.replace("_", ":")

    def target2(*args, **kargs):
        signal.signal(signal.SIGINT, signal.SIG_IGN) # @@ aargh!
        target(*args, **kargs)

    kargs = {"target": target2, "args": args, "name": name}
    p = multiprocessing.Process(**kargs)
    p.start()
    return p

def create_database_interface(base, manager):
    import os.path
    import pickle
    import json
    import contextlib

    cache = manager.Namespace()
    lock = multiprocessing.RLock()

    base = os.path.expanduser(base)
    dotdb = base + ".%s.db"
    dotjson = base + ".%s.json"

    def check(name):
        if not name.isalpha():
            raise ValueError(name)

    def do_load(name):
        filename = dotdb % name
        if os.path.isfile(filename):
            with open(filename, "rb") as f:
                return pickle.load(f)

    def do_dump(name, data):
        with open(dotdb % name, "wb") as f:
            pickle.dump(data, f)

    # @@ init, copies to cache returns a fallback?
    # e.g. irc.safe.database.init("name", [])

    def init(name, default=None):
        data = do_load(name) or default
        setattr(cache, name, data)
        if data is default:
            do_dump(name, data)

    def load(name):
        check(name)
        with lock:
            return do_load(name)

    def dump(name, data):
        check(name)
        with lock:
            do_dump(name, data)

    @contextlib.contextmanager
    def context(name):
        check(name)
        with lock:
            data = getattr(cache, name)
            yield data
            setattr(cache, name, data)
            do_dump(name, data)

    def export(name): # remove this? export base instead?
        check(name)
        with lock:
            data = do_load(name)
            filename = dotjson % name
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f)
            return filename

    return duxlot.FrozenStorage({
        "init": init,
        "load": load,
        "dump": dump,
        "context": context,
        "export": export,
        "cache": cache,
        "lock": lock
    })

comment = """
def main(name=None):
    import os.path
    import json

    if name is None:
        name = os.path.expanduser("~/.duxlot")

    with open(name) as f:
        config = json.load(f)

    Client(config)
"""

if __name__ == "__main__":
    ... # main()

# eof
