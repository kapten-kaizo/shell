#!/data/data/com.termux/files/usr/bin/python
# Modify script By KangEhem
# Original Repo Link : https://github.com/lmacken/pyrasite
# Time Generate Script 30 nov 2021 19.57
# Don't Forget to follow my github profile
# for more information visit the Original repo link
import os, sys
import socket
import struct
import tempfile
import subprocess
import traceback
import threading
from code import InteractiveConsole

if sys.version_info[0] == 3:
    from io import StringIO
else:
    from StringIO import StringIO

from os.path import dirname, abspath, join
__version__ = '2.0'
pyvers = sys.version.split()[0]

class PyrasiteIPC(object):
    reliable = True

    def __init__(self, pid, reverse='ReversePythonConnection'):
        super(PyrasiteIPC, self).__init__()
        self.pid = pid
        self.sock = None
        self.server_sock = None
        self.hostname = None
        self.port = None
        self.reverse = reverse

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args, **kwargs):
        self.close()

    @property
    def title(self):
        if not getattr(self, '_title', None):
            p = subprocess.Popen('ps --no-heading -o cmd= -p %d' % self.pid,
                                 stdout=subprocess.PIPE, shell=True)
            self._title = p.communicate()[0].decode('utf-8')
        return self._title.strip()

    def connect(self):
        """
        Setup a communication socket with the process by injecting
        a reverse subshell and having it connect back to us.
        """
        self.listen()
        self.inject()
        self.wait()

    def listen(self):
        """Listen on a random port"""
        for res in socket.getaddrinfo('localhost', None, socket.AF_UNSPEC,
                                      socket.SOCK_STREAM, 0, 0):
            af, socktype, proto, canonname, sa = res
            try:
                self.server_sock = socket.socket(af, socktype, proto)
                try:
                    self.server_sock.bind(sa)
                    self.server_sock.listen(1)
                except socket.error:
                    self.server_sock.close()
                    self.server_sock = None
                    continue
            except socket.error:
                self.server_sock = None
                continue
            break

        if not self.server_sock:
            raise Exception('pyrasite was unable to setup a ' +
                    'local server socket')
        else:
            self.hostname, self.port = self.server_sock.getsockname()[0:2]

    def PyrasiteINJECT(self, pid, filename, verbose=False, gdb_prefix=''):
        """Executes a file in a running Python process."""
        filename = os.path.abspath(filename)
        gdb_cmds = [
        '((int (*)())PyGILState_Ensure)()',
        '((int (*)(const char *))PyRun_SimpleString)("'
            'import sys; sys.path.insert(0, \\"%s\\"); '
            'sys.path.insert(0, \\"%s\\"); '
            'exec(open(\\"%s\\").read())")' %
                (os.path.dirname(filename),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
                filename),
        '((void (*) (int) )PyGILState_Release)($1)',
        ]
        cmd = '%sgdb -p %d -batch %s' % (gdb_prefix, pid, ' '.join(["-eval-command='call %s'" % cmd for cmd in gdb_cmds]))
        p = subprocess.Popen(cmd,
            shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        if verbose:
            print(out)
            print(err)

    def create_payload(self):
        """Write out a reverse python connection payload with a custom port"""
        (fd, filename) = tempfile.mkstemp()
        tmp = os.fdopen(fd, 'w')
        ripgrep = open(__file__, "r").read()
        line = ripgrep.replace("source = '''", '')
        line = line.replace("port = 9001", "port = %d" % self.port)
        if not self.reliable:
            line = line.replace("reliable = True", "reliable = False")
        line = line.replace("self.close()'''","self.close()")
        line = line.replace("PyrasiteStart()","%s().start()" % self.reverse)
        tmp.write(line)
        tmp.close()
        return filename

    def inject(self):
        """Inject the payload into the process."""
        filename = self.create_payload()
        self.PyrasiteINJECT(self.pid, filename)
        os.unlink(filename)

    def wait(self):
        """Wait for the injected payload to connect back to us"""
        (clientsocket, address) = self.server_sock.accept()
        self.sock = clientsocket
        self.sock.settimeout(5)
        self.address = address

    def cmd(self, cmd):
        """
        Send a python command to exec in the process and return the output
        """
        self.send(cmd + '\n')
        return self.recv()

    def send(self, data):
        """Send arbitrary data to the process via self.sock"""
        header = ''.encode('utf-8')
        data = data.encode('utf-8')
        if self.reliable:
            header = struct.pack('<L', len(data))
        self.sock.sendall(header + data)

    def recv(self):
        """Receive a command from a given socket"""
        if self.reliable:
            header_data = self.recv_bytes(4)
            if len(header_data) == 4:
                msg_len = struct.unpack('<L', header_data)[0]
                data = self.recv_bytes(msg_len).decode('utf-8')
                if len(data) == msg_len:
                    return data
        else:
            return self.sock.recv(4096).decode('utf-8')

    def recv_bytes(self, n):
        """Receive n bytes from a socket"""
        data = ''.encode('utf-8')
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                break
            data += chunk
        return data

    def close(self):
        if self.sock:
            self.sock.close()
        if getattr(self, 'server_sock', None):
            self.server_sock.close()

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, self.pid)


def PyrasiteStart(x=None):
    """Open a Python shell in a running process"""

    if not len(sys.argv) == 2:
        print("Usage: pyrasite-shell <PID>")
        sys.exit(1)

    ipc = PyrasiteIPC(int(sys.argv[1]), 'ReversePythonShell')
    ipc.connect()

    print("Pyrasite Shell %s" % __version__)
    print("Connected to '%s'" % ipc.title)
    prompt, payload = ipc.recv().split('\n', 1)
    print(payload)

    try:
        import readline
    except ImportError:
        pass

    # py3k compat
    try:
        input_ = raw_input
    except NameError:
        input_ = input

    try:
        while True:
            try:
                input_line = input_(prompt)
            except EOFError:
                input_line = 'exit()'
                print('')
            except KeyboardInterrupt:
                input_line = 'None'
                print('')

            ipc.send(input_line)
            payload = ipc.recv()
            if payload is None:
                break
            prompt, payload = payload.split('\n', 1)
            if payload != '':
                print(payload)
    except:
        print('')
        raise

    ipc.close()

source = '''
class DistantInteractiveConsole(InteractiveConsole):
    def __init__(self, ipc):
        InteractiveConsole.__init__(self, globals())

        self.ipc = ipc
        self.set_buffer()

    def set_buffer(self):
        self.out_buffer = StringIO()
        sys.stdout = sys.stderr = self.out_buffer

    def unset_buffer(self):
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__
        value = self.out_buffer.getvalue()
        self.out_buffer.close()

        return value

    def raw_input(self, prompt=""):
        output = self.unset_buffer()
        self.ipc.send('\n'.join((prompt, output)))

        cmd = self.ipc.recv()

        self.set_buffer()

        return cmd


class ReversePythonShell(threading.Thread, PyrasiteIPC):
    """A reverse Python shell that behaves like Python interactive interpreter.

    """

    host = 'localhost'
    port = 9001
    reliable = True

    def __init__(self, host=None, port=None):
        super(ReversePythonShell, self).__init__()

    def run(self):
        try:
            for res in socket.getaddrinfo(self.host, self.port,
                    socket.AF_UNSPEC, socket.SOCK_STREAM):
                af, socktype, proto, canonname, sa = res
                try:
                    self.sock = socket.socket(af, socktype, proto)
                    try:
                        self.sock.connect(sa)
                    except socket.error:
                        self.sock.close()
                        self.sock = None
                        continue
                except socket.error:
                    self.sock = None
                    continue
                break

            if not self.sock:
                raise Exception('pyrasite cannot establish reverse ' +
                        'connection to %s:%d' % (self.host, self.port))

            DistantInteractiveConsole(self).interact()

        except SystemExit:
            pass
        except:
            traceback.print_exc(file=sys.__stderr__)

        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__
        self.close()'''
PyrasiteStart()

