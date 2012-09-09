#!/usr/bin/env python3
# @@ -Ou

# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

import queue
import re
import socket
import threading
import time

import api

def nick():
    import random
    rare = "zqxjkvbpyg"
    return "".join(random.choice(rare) for i in range(8))

class Client(object):
    def __init__(self, options):
        self.socket = socket.socket(socket.AF_INET, socket.TCP_NODELAY)
        self.socket.connect(("irc.freenode.net", 6667))

        if not ("nick" in options):
            options["nick"] = nick()

        self.safe = type("Safe", (object,), {
            "__slots__": [],
            "received": queue.Queue(),
            "sending": queue.Queue(),
            "sockfile": self.socket.makefile("rb"),
            "send": self.socket.send,
            "options": options
        })()

        self.thread(self.receive_thread)
        self.thread(self.send_thread)

        self.put = self.safe.sending.put

        self.send("NICK " + self.safe.options["nick"])
        self.send("USER test 8 * duxlot/test.py")
        self.send("JOIN " + self.safe.options["channel"])

        self.tests = []
        self.setup()

        while True:
            item = self.safe.received.get()
            if item["command"] == "366": # End of NAMES list
                if item["parameters"][1] == self.safe.options["channel"]:
                    break

        while True:
            item = self.safe.received.get()
            if item["command"] == "PRIVMSG":
                if item["parameters"][0] == self.safe.options["channel"]:
                    if item["parameters"][1] == "start!":
                        break

        self.test()

    def send(self, text):
        self.put(text.encode("utf-8"))

    def setup(self):
        def constructor(command):
            def append(text):
                self.tests.append((command, text))
            return append

        send = constructor("send")
        receive = constructor("receive")
        match = constructor("match")
        search = constructor("search")

        # Tests

        with open("data/tests.txt") as f:
            for line in f:
                line = line.rstrip("\r\n")
                if not line:
                    continue

                line = line.replace("$(BOT)", self.safe.options["bot"])
                line = line.replace("$(USER)", self.safe.options["nick"])

                if line.startswith("."):
                    self.tests.append(("send", line))

                else:
                    if line.startswith(": "):
                        line = self.safe.options["nick"] + line

                    if "<" in line:
                        patterns = []
                        for part in re.findall("<[^>]+>|[^<]+", line):
                            if part.startswith("<"):
                                patterns.append(part[1:-1])
                            else:
                                patterns.append(re.escape(part))
                        self.tests.append(("match", "".join(patterns)))
                    else:
                        self.tests.append(("receive", line))

        send(self.safe.options["bot"] + "!")
        receive("$(nick)!")

    def test(self):
        def received(item, text):
            return item["parameters"][1] == text

        def matched(item, text):
            print(text)
            print(re.match("^%s$" % text, item["parameters"][1]))
            return re.match("^%s$" % text, item["parameters"][1]) is not None

        def searched(item, text):
            return re.search(text, item["parameters"][1]) is not None

        for command, text in self.tests:
            text = text.replace("$(nick)", self.safe.options["nick"])
            channel = self.safe.options["channel"]

            if command == "send":
                if text.startswith("."):
                    text = self.safe.options["prefix"] + text[1:] # @@
                    # text = "." + text # @@                
                self.send("PRIVMSG " + channel + " :" + text)

            elif command in {"receive", "match", "search"}:
                timeout = 10
                start = time.time()
                while True:
                    try: item = self.safe.received.get(timeout=timeout)
                    except queue.Empty:
                        print("Timed out!")
                        self.send("PRIVMSG " + channel + " :sbp: Timed out!")
                        item = None
                        break

                    if item["command"] == "PRIVMSG":
                        if item["prefix"]["nick"] == self.safe.options["bot"]:
                            break

                    timeout = 10 - (time.time() - start)
                    if timeout <= 0:
                        print("Timed out!")
                        self.send("PRIVMSG " + channel + " :sbp: Timed out!")
                        item = None
                        break

                if item:                    
                    success = {
                        "receive": received,
                        "match": matched,
                        "search": searched
                    }[command]

                    if success(item, text):
                        print("Success")
                    else:
                        print("Failure")
                        FAILURE = "----- FAILURE! -----"
                        self.send("PRIVMSG " + channel + " :sbp: " + FAILURE)
                        self.send("PRIVMSG " + channel + " :Expected: " + text)

            time.sleep(1)

    def thread(self, method):
        t = threading.Thread(target=method, args=(self.safe,))
        t.start()

    @staticmethod
    def receive_thread(safe):
        for line in safe.sockfile:
            print(line)
            parsed = api.irc.parse_message(octets=line)()
            # print(parsed)
            if parsed["command"] == "PING":
                nick = safe.options["nick"].encode("us-ascii")
                safe.send(b"PONG :" + nick + b"\r\n")
            safe.received.put(parsed)

    @staticmethod
    def send_thread(safe):
        while True:
            octets = safe.sending.get()
            if octets is StopIteration:
                break
            if not isinstance(octets, bytes):
                continue
            octets = octets.replace(b"\r", b"")
            octets = octets.replace(b"\n", b"")
            octets = octets[:510] + b"\r\n"
            safe.send(octets)
            print("->", octets)
            time.sleep(1)

def main():
    import os.path
    import json

    with open(os.path.expanduser("~/.duxlot-test")) as f:
        config = json.load(f)

    Client(config)

if __name__ == "__main__":
    main()

# eof
