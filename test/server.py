# Copyright 2012, Sean B. Palmer
# Code at http://inamidst.com/duxlot/
# Apache License 2.0

import multiprocessing
import os
import re
import socket
import socketserver
import sys
import time

if not os.path.isfile("duxlot"):
    print("Error: Not running in the duxlot directory")
    sys.exit(1)

sys.path[:0] = [os.getcwd()]

# Save PEP 3122!
if "." in __name__:
    from . import api
else:
    import api

connections = 0
test_counter = 0
tests = {}

def test(test_function):
    global test_counter

    def decorated(conn):
        test_function(conn)

    test_counter += 1
    decorated.number = test_counter
    tests[decorated.number] = decorated
    return decorated

# @@ quit from a test, then start a new instance

# @test
def test_timeout(conn):
    conn.handshake()
    conn.nowt()

@test
def test_admin(conn):
    conn.handshake()
    conn.send(":admin01", "PRIVMSG", "#duxlot", ".prefix ^")
    msg = conn.recv()
    conn.equal(msg["command"], "PRIVMSG", "Not a PRVIMSG")

    conn.send(":user", "PRIVMSG", "#duxlot", "^utc")
    msg = conn.recv()
    conn.equal(msg["command"], "PRIVMSG", "Not a PRVIMSG")

    # Change it back for other tests
    conn.send(":admin01", "PRIVMSG", "#duxlot", "^prefix .")
    msg = conn.recv()
    conn.equal(msg["command"], "PRIVMSG", "Not a PRVIMSG")

with open("test/combined.txt", encoding="utf-8") as f:
    text = f.read()

for lines in text.split("\n\n"):
    def build(lines):
        lines = lines.rstrip("\n")
        if not lines:
            return
        # if not lines.startswith(".tw"):
        #     return

        # @@ expected
        @test
        def test_function(conn):
            conn.handshake()
    
            for line in lines.split("\n"):
                line = line.replace("$(BOT)", "duxlot")
                line = line.replace("$(USER)", "user")
    
                if line.startswith("."):
                    conn.send(":user!~user@localhost", "PRIVMSG", "#duxlot", line)
                elif line == "TIMEOUT":
                    conn.nowt()
                elif line.startswith("WAIT "):
                    time.sleep(int(line.split(" ").pop().strip()))
                elif line.startswith("SAY"):
                    line = line.split(" ", 1).pop()
                    conn.send(":user!~user@localhost", "PRIVMSG", "#duxlot", line)
                else:
                    if line.startswith(": "):
                        line = "user" + line
                    got = conn.recv()
                    conn.equal(got.get("command"), "PRIVMSG",
                        "Expected PRIVMSG, got %s" % got)
                    # @@ check it's to #duxlot
                    got = got["parameters"][1]
    
                    if "<" in line:
                        patterns = []
                        for part in re.findall("<[^>]+>|[^<]+", line):
                            if part.startswith("<"):
                                patterns.append(part[1:-1])
                            else:
                                patterns.append(re.escape(part))
                        pattern = "^" + "".join(patterns) + "$"
                        conn.match(pattern, got, "Expected %r, got %r" % (pattern, got))
                    else:
                        conn.equal(line, got, "Expected %r, got %r" % (line, got))
                # @@ then a nowt?
    build(lines[:])

# @test
def test_scheduler(conn):
    conn.handshake()
    time.sleep(60)

# @test
def test_maximum_processes(conn):
    conn.handshake()
    for i in range(6):
        conn.send(":owner!~owner@localhost", "PRIVMSG", "duxlot", ".test-hang")
        # conn.recv()
        time.sleep(1)
    time.sleep(30)

@test
def test_hang(conn):
    conn.handshake()
    conn.send(":owner!~owner@localhost", "PRIVMSG", "duxlot", ".test-hang")
    time.sleep(1)

# @test
def quit1(conn):
    conn.handshake()
    conn.send(":owner!~owner@localhost", "PRIVMSG", "duxlot", ".quit")

@test
def quit(conn):
    conn.send(":localhost", "NOTICE", "*", "Welcome!")
    conn.send(":owner!~owner@localhost", "PRIVMSG", "duxlot", ".quit")
    time.sleep(2)

class Test(socketserver.StreamRequestHandler):
    timeout = 6

    def handle(self, *args, **kargs):
        global connections, test_counter

        connections += 1
        self.connection = connections
        self.messages = 0

        # print(dir(self.server))
        self.send(":localhost", "NOTICE", "*", "Test #%s" % self.connection)

        if self.connection in tests:
            print("Test #%s" % self.connection)
            tests[self.connection](self)

            # print(self.connection, test_counter)
            if self.connection == test_counter:
                print("Tests complete")
                self.finish()
                os._exit(0)

    def match(self, a, b, message):
        if not re.match(a, b):
            print("ERROR: Test #%s: %s" % (self.connection, message))
            self.stop()

    def equal(self, a, b, message):
        if a != b:
            print("ERROR: Test #%s: %s" % (self.connection, message))
            self.stop()

    def not_equal(self, a, b, message):
        if a == b:
            print("ERROR: Test #%s: %s" % (self.connection, message))
            self.stop()

    def stop(self):
        sys.exit(0)

    def handshake(self):
        nick = self.recv()
        self.equal(nick["command"], "NICK", "Expected NICK")

        user = self.recv()
        self.equal(user["command"], "USER", "Expected USER")

        join = self.recv()
        self.equal(join["command"], "JOIN", "Expected JOIN")

        who = self.recv()
        self.equal(who["command"], "WHO", "Expected WHO")

    def recv(self):
        try: octets = self.rfile.readline()
        except socket.timeout:
            print("ERROR: Test #%s: timeout" % self.connection)
            self.stop()

        o = api.irc.parse_message(octets=octets)
        self.messages += 1
        o.count = self.messages
        return o()

    def nowt(self):
        try: octets = self.rfile.readline()
        except socket.timeout:
            return True
        else:
            text = octets.decode("utf-8", "replace")
            args = (self.connection, text)
            print("ERROR: Test #%s: Expected timeout, got %r" % args)

    def send(self, *args):
        args = list(args)
        if len(args) > 1:
            args[-1] = ":" + args[-1]
        octets = " ".join(args).encode("utf-8", "replace")
        octets = octets.replace(b"\r", b"")
        octets = octets.replace(b"\n", b"")
        if len(octets) > 510:
            octets = octets[:510]
        self.wfile.write(octets + b"\r\n")
        self.wfile.flush()

    # def user
    # def channel

    def finish(self, *args, **kargs):
        socketserver.StreamRequestHandler.finish(self)

        try:
            self.request.shutdown(socket.SHUT_RDWR)
            self.request.close()
        except socket.error:
            ...

class Server(socketserver.TCPServer):
    ...

    # @@ if SystemExit, fine, otherwise raise it and os._exit(1)
    def handle_error(self, request, client_address):
        etype, evalue, etrace = sys.exc_info()
        if etype is SystemExit:
            return

        import traceback
        print("Framework Error:", etype, evalue)
        traceback.print_exc()
        os._exit(1)

def main():
    server = Server(("", 61070), Test)
    server.serve_forever()

if __name__ == "__main__":
    main()
