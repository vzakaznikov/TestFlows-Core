# Copyright 2019 Katteli Inc.
# TestFlows Test Framework (http://testflows.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import io
import sys
import csv
import argparse

from argparse import ArgumentTypeError
from collections import namedtuple
from testflows._core.exceptions import exception
from testflows._core.compress import CompressedFile
from testflows._core.funcs import repeat as Repeat

KeyValue = namedtuple("KeyValue", "key value")

class FileType(object):
    def __init__(self, mode='r', bufsize=-1, encoding=None, errors=None):
        self._mode = mode
        self._bufsize = bufsize
        self._encoding = encoding
        self._errors = errors

    def __call__(self, string):
        # the special argument "-" means sys.std{in,out}
        if string == '-':
            if 'r' in self._mode:
                if 'b' in self._mode:
                    return sys.stdin.buffer
                return sys.stdin
            elif 'w' in self._mode:
                if 'b' in self._mode:
                    return sys.stdout.buffer
                return sys.stdout
            else:
                msg = argparse._('argument "-" with mode %r') % self._mode
                raise ValueError(msg)

        # all other arguments are used as file names
        try:
            return open(string, self._mode, self._bufsize, self._encoding,
                        self._errors)
        except OSError as e:
            message = argparse._("can't open '%s': %s")
            raise ArgumentTypeError(message % (string, e))

    def __repr__(self):
        args = self._mode, self._bufsize
        kwargs = [('encoding', self._encoding), ('errors', self._errors)]
        args_str = ', '.join([repr(arg) for arg in args if arg != -1] +
                             ['%s=%r' % (kw, arg) for kw, arg in kwargs
                              if arg is not None])
        return '%s(%s)' % (type(self).__name__, args_str)

class LogFileType(object):
    def __init__(self, mode='r', bufsize=-1, encoding=None, errors=None):
        self._mode = mode
        self._encoding = encoding
        self._errors = errors

    def __call__(self, string):
        # the special argument "-" means sys.std{in,out}
        if string == '-':
            if 'r' in self._mode:
                fp = CompressedFile(sys.stdin.buffer, self._mode)
                if self._encoding:
                    return io.TextIOWrapper(fp, self._encoding, self._errors)
                return fp
            elif 'w' in self._mode:
                fp = CompressedFile(sys.stdout.buffer, self._mode)
                if self._encoding:
                    return io.TextIOWrapper(fp, self._encoding, self._errors)
                return fp
            else:
                msg = argparse._('argument "-" with mode %r') % self._mode
                raise ValueError(msg)

        # all other arguments are used as file names
        try:
            fp = CompressedFile(string, self._mode)
            if self._encoding:
                return io.TextIOWrapper(fp, self._encoding, self._errors)
            return fp
        except OSError as e:
            message = argparse._("can't open '%s': %s")
            raise ArgumentTypeError(message % (string, e))

    def __repr__(self):
        args = self._mode
        kwargs = [('encoding', self._encoding), ('errors', self._errors)]
        args_str = ', '.join([repr(arg) for arg in args if arg != -1] +
                             ['%s=%r' % (kw, arg) for kw, arg in kwargs
                              if arg is not None])
        return '%s(%s)' % (type(self).__name__, args_str)


def file(*args, **kwargs):
    """File type."""
    return FileType(*args, **kwargs)

def logfile(*args, **kwargs):
    """Log file type."""
    return LogFileType(*args, **kwargs)

def key_value(s, sep='='):
    """Parse a key, value pair using a seperator (default: '=').
    """
    if sep not in s:
        raise ArgumentTypeError(f"invalid format of key{sep}value")
    key, value= s.split(sep, 1)
    return KeyValue(key.strip(), value.strip())

def count(value):
    try:
        value = int(value)
        assert value >= 0
    except:
        raise ArgumentTypeError(f"{value} is not a positive number")
    return value

def repeat(value):
    try:
        fields = list(csv.reader([value],"unix"))[-1]
        option = Repeat(*fields)
    except Exception as e:
        raise ArgumentTypeError(f"'{value}' is invalid")
    return option
