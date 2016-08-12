# encoding: utf-8

from contextlib import contextmanager
import cStringIO
import os.path
from subprocess import Popen, PIPE, call
import sys
import threading

ROOTDIR = os.path.dirname(os.path.abspath(__file__))


# ======================= GENERAL UTILILITIES =======================

def extract_column(text, column, start=0, sep=None):
    """ Extracts columns from a formatted text
    :param text:
    :param column: the column number: from 0, -1 = last column
    :param start: the line number to start with (headers removal)
    :param sep: optional separator between words  (default is arbitrary number of blanks)
    :return: a list of words
    """
    lines = text.splitlines() if isinstance(text, basestring) else text
    if start:
        lines = lines[start:]
    values = []
    for line in lines:
        elts = line.split(sep) if sep else line.split()
        if elts and column < len(elts):
            values.append(elts[column].strip())
    return values


def filter_column(text, column, start=0, sep=None, **kwargs):
    """ Filters (like grep) lines of text according to a specified column and operator/value
    :param text: a string
    :param column: integer >=0
    :param sep: optional separator between words  (default is arbitrary number of blanks)
    :param kwargs: operator=value eg eq='exact match', contains='substring', startswith='prefix' etc...
    :return:
    """
    if len(kwargs) != 1:
        raise TypeError("Missing or too many keyword parameter in filter_column")
    op, value = kwargs.items()[0]
    if op in ('eq', 'equals'):
        op = '__eq__'
    elif op in ('contains', 'includes'):
        op = '__contains__'
    elif not op in ('startswith', 'endswith'):
        raise ValueError("Unknown filter_column operator: {}".format(op))
    lines = text.splitlines() if isinstance(text, basestring) else text
    if start:
        lines = lines[start:]
    values = []
    for line in lines:
        elts = line.split(sep) if sep else line.split()
        if elts and column < len(elts):
            elt = elts[column]
            if getattr(elt, op)(value):
                values.append(line.strip())
    return values


class Sequencer(object):
    def run_sequence(self, args):
        for arg in args:
            if isinstance(arg, basestring):
                getattr(self, arg)()
            else:
                getattr(self, arg[0])(*(arg[1:]))
        return self


# ======================= OS RELATED UTILITIES =======================

# this is a direct copy from fabric
def _wrap_with(code):
    def inner(text, bold=False):
        c = code
        if bold:
            c = "1;%s" % c
        return "\033[%sm%s\033[0m" % (c, text)
    return inner

red = _wrap_with('31')
green = _wrap_with('32')
yellow = _wrap_with('33')
blue = _wrap_with('34')
magenta = _wrap_with('35')
cyan = _wrap_with('36')
white = _wrap_with('37')


@contextmanager
def cd(folder):
    old_folder = os.getcwd()
    try:
        yield os.chdir(folder)
    finally:
        os.chdir(old_folder)


COMMAND_DEBUG = None
# COMMAND_DEBUG = 'Debug: '


class Command(object):
    """ Use this class if you want to wait and get shell command output
    """
    def __init__(self, cmd, show=COMMAND_DEBUG):
        self.show = show
        self.p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
        self.out_buf = cStringIO.StringIO()
        self.err_buff = cStringIO.StringIO()
        t_out = threading.Thread(target=self.out_handler)
        t_err = threading.Thread(target=self.err_handler)
        t_out.start()
        t_err.start()
        self.p.wait()
        t_out.join()
        t_err.join()
        self.p.stdout.close()
        self.p.stderr.close()
        self.stdout = self.out_buf.getvalue()
        self.stderr = self.err_buff.getvalue()
        self.returncode = self.p.returncode

    def out_handler(self):
        for line in iter(self.p.stdout.readline, ''):
            if self.show is not None:
                sys.stdout.write(self.show + line)
            self.out_buf.write(line)

    def err_handler(self):
        for line in iter(self.p.stderr.readline, ''):
            if self.show is not None:
                sys.stderr.write(self.show + 'Error: ' + line)
            self.err_buff.write(line)

    def stdout_column(self, column, start=0):
        return extract_column(self.stdout, column, start)


def command(cmd, raises=False):
    """ Use this function if you only want the return code.
        You can't retrieve stdout nor stderr and it never raises
    """
    ret = call(cmd, shell=True)
    if ret and raises:
        raise RuntimeError("Error while executing<{}>".format(cmd))
    return ret


def command_input(cmd, datain, raises=False):
    """ Use this if you want to send data to stdin
    """
    p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    p.communicate(datain)
    if p.returncode and raises:
        raise RuntimeError("Error while executing<{}>".format(cmd))
    return p.returncode


def ssh(cmd, host, user='root', raises=True):
    """ Executes ssh on host if host's ~/.ssh/authorized_keys contains images/keys/unsecure_key.pub
    :param cmd: command to execute on host (beware quotes)
    :param host: host's ip
    :param user: usually 'root'
    :param raises: if True, will raise if return code is nonzero
    :return: string: command's stdout
    """
    keys = os.path.join(ROOTDIR, 'images/keys/unsecure_key')
    ssh = Command('ssh -o StrictHostKeyChecking=no -i {keys} {user}@{host} {cmd}'.format(**locals()))
    if ssh.returncode and raises:
        raise RuntimeError("Command '{}' on host {} returned an error:\n{}".format(cmd, host, ssh.stderr))
    return ssh.stdout


def scp(source, dest, host, user='root'):
    """ source and dest must be absolute paths
    """
    keys = os.path.join(ROOTDIR, 'images/keys/unsecure_key')
    return command('scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -i {keys} '
             '{source} {user}@{host}:{dest}'.format(**locals()))


# =================== REMOTE HOSTS RELATED UTILITIES =======================


def get_processes(platform, host):
    return extract_column(platform.docker_exec('ps -A', host), -1, 1)


def get_version(platform, app, host):
    text = platform.docker_exec('apt-cache policy {}'.format(app), host)
    try:
        return extract_column(filter_column(text, 0, startswith='Install'), 1, sep=':')[0]
    except IndexError:
        return None

