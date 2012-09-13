# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

import multiprocessing
import os
import signal
import socket
import sys
import time

# Save PEP 3122!
if "." in __name__:
    from . import storage
else:
    import storage
debug = storage.output.write
del storage

class Process(object):
    def __init__(self, name):
        self.name = name

        self.function = None
        self.storage = None

        self.process = None
        self.started = None
        self.terminated = False

        self.inactive = multiprocessing.Event()
        self.inactive.set()

    def action(self, function, storage):
        self.function = function
        self.storage = storage

    def start(self):
        if self.active:
            return

        def wrapper(self):
            self.inactive.clear()
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            self.function(self.storage)
            self.inactive.set()

        self.process = multiprocessing.Process(
            target=wrapper,
            name=self.name,
            args=(self,) # @@ freeze?
        )

        self.process.start()
        self.started = time.time()

    def duration(self):
        if self.started is None:
            return None
        return time.time() - self.started

    @property
    def active(self):
        # self.process.is_alive() is *unreliable*
        return not self.inactive.is_set()

    def finish(self):
        ...

    def stop(self, finish=False, timeout=6):
        if finish is True:
            self.finish()

        if self.active:
            try: self.process.join(timeout / 2)
            except AssertionError:
                debug("Got join() error in", self.name)
                self.inactive.wait(timeout)
            self.inactive.wait(timeout / 2)

            if self.active:
                debug("Sending SIGTERM to process:%s" % self.name)
                debug("And self.process is...", self.process)
                try: self.process.terminate()
                except AttributeError:
                    debug("Got attribute error in", self.name)
                self.terminated = True

            # debug("Had to SIGTERM, exiting")
            # import sys
            # sys.exit()

    def terminate(self):
        try: self.process.terminate()
        except Exception as err:
            debug("Asked to TERM", self.name, err)

class SocketProcess(Process):
    def __init__(self, name, create_socket):
        Process.__init__(self, name)
        self.create_socket = create_socket

    def start(self):
        self.socket = self.create_socket()
        self.storage.socket = self.socket
        Process.start(self)

    def finish(self):
        if self.active and (self.socket is not None):
            try: self.socket.shutdown(socket.SHUT_RDWR)
            except socket.error:
                ...
            finally:
                self.socket = None

class QueueProcess(Process):
    def __init__(self, name):
        Process.__init__(self, name)
        self.queue = multiprocessing.JoinableQueue()

    def action(self, function, storage):
        Process.action(self, function, storage)
        self.storage.queue = self.queue.get

    def finish(self):
        if self.active:
            self.queue.put("StopIteration")

class Processes(object):
    def __init__(self, create_socket):
        self.socket = "receive"
        self.queues = ("send", "messages", "events", "schedule")
        self.processes = {}
        self.queue = multiprocessing.JoinableQueue()
        self.commands = multiprocessing.Value("i", 0)
        self.lock = multiprocessing.Lock()
        self.create_socket = create_socket
        self.create()

    def __getitem__(self, key):
        return self.processes[key]

    def __setitem__(self, key, value):
        self.processes[key] = value

    def create(self):
        "Create socket and queue processes"
        self[self.socket] = SocketProcess(self.socket, self.create_socket)

        for process_name in self.queues:
            self[process_name] = QueueProcess(process_name)

    def start(self):
        "Start all processes"
        self[self.socket].start()

        self.resume()

    def stop(self):
        "Stop all processes"
        self.pause()

        self[self.socket].finish()
        self[self.socket].stop()

    def terminate(self):
        "Send a SIGTERM to all processes"
        for name in (self.socket,) + self.queues:
            self[name].terminate()

    def pause(self):
        "Stop all queue processes"
        for process_name in reversed(self.queues):
            self[process_name].finish()

        for process_name in reversed(self.queues):
            self[process_name].stop()

    def resume(self):
        "Start all queue processes"
        for process_name in self.queues:
            debug("Calling start on", process_name)
            self[process_name].start()

    def flush(self):
        "Create new queues"
        # self.stop()

        for process_name in reversed(self.queues):
            if process_name == "messages":
                continue
            process = self[process_name]
            debug("Flushing the queue of", process_name)
            process.queue = multiprocessing.JoinableQueue()

        # self.start()

    def empty(self):
        "Empty queues"
        import queue

        for process_name in reversed(self.queues):
            while True:
                try: self[process_name].queue.get_nowait()
                except queue.Empty:
                    break

    @property
    def number(self):
        return len(multiprocessing.active_children())

class Commands(object):
    def __init__(self, manager, schedule):
        self.lock = multiprocessing.Lock()
        self.number = manager.Value("i", 0)
        self.active = manager.Value("i", 0)
        self.known = manager.dict()
        self.pid = manager.dict()
        self.schedule = schedule

    def __contains__(self, name):
        return name in self.known

    def __getitem__(self, name):
        # @@ call this get?
        # @@ while name in self?
        for process in multiprocessing.active_children():
            debug("Running", process.name, process)
            if process.name == name:
                return process

    def __iter__(self):
        for process in multiprocessing.active_children():
            if process.name.startswith("Command "):
                yield process

    def spawn(self, function, storage):
        if self.active.value >= 3:
            debug("Command failed: too many active processes")
            return False

        def process(self, name, function, storage):
            debug(name, "starting")
            with self.lock:
                self.active.value += 1
                created = self.known[name][0]
                self.known[name] = [created, time.time()]

            def exit(signum, frame):
                with self.lock:
                    self.active.value -= 1
                    del self.known[name]
                    del self.pid[name]
                sys.exit(1)
            # This MUST be set for self.terminate_command to work
            # Otherwise it propagates up to process:main
            signal.signal(signal.SIGTERM, exit)
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            try: function(storage)
            finally:
                with self.lock:
                    if name in self.known:
                        self.active.value -= 1
                        del self.known[name]
                        del self.pid[name]
                debug(name, "stopping")

        with self.lock:
            self.number.value += 1

        name = "Command %05i" % self.number.value
        self.known[name] = [time.time(), False]
        p = multiprocessing.Process(
            target=process,
            name=name,
            args=(self, name, function, storage)
        )
        p.start()
        self.pid[name] = p.pid

        # time.time() + 60
        # self.schedule
        return name

    def terminate_command(self, name):
        pid = self.pid.get(name)
        if pid:
            # There must be a signal handler set in the process
            debug("Sending SIGTERM to", name)
            try: os.kill(pid, signal.SIGTERM)
            except Exception as err:
                return False
            return True

        debug("Couldn't SIGTERM %s!" % name)
        return False

    def collect(self, timeout=60):
        count = 0
        current = time.time()

        items = list(self.known.items())
        for name, info in items:
            created, started = info
            if not started:
                continue

            # @@ if (started - created) > N, penalise less
            if current > (started + timeout):
                terminated = self.terminate_command(name)
                if terminated:
                    count += 1

        return count

    def collectable(self, timeout=60):
        count = 0
        current = time.time()

        items = list(self.known.items())
        for name, info in items:
            created, started = info
            if not started:
                continue
            if current > (started + timeout):
                count += 1

        debug("Collectable:", count, "of", len(items))
        return count
