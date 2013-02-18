#!/usr/bin/python
# -*- coding: utf-8 -*-

#
# Licensed under the GNU General Public License Version 2 or later
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

# Copyright (C) 2012-2013
#    Francisco Dos Santos <f.dos.santos@free.fr>

"""
Log file and progress status.
"""

import sys, time

#
# Globals
#
level = 0
stdout = sys.stdout
quiet = True
filelog = None
inprogress = ''   # '\n' when stdout is not on the first column
progressmax = 0
progresstext = ''
progressnext = 0
progresstimer = 0.0
progresscpt = 0


#
# Functions
#

def WARN(text):
    """
    Write a warning message to stdout and the log file.
    """

    global inprogress

    if text[-1] == '\n':
        text = "WARN: " + text
    else:
        text = "WARN: " + text + "\n"
    if not quiet:
        stdout.write(inprogress + text)
        stdout.flush()
        inprogress = ''
    if filelog:
        filelog.write(text)


def ERROR(text):
    """
    Write an error message to stdout and the log file.
    Return an Exception object so the caller can raise it.
    """

    global inprogress

    inst = Exception(text)
    if text[-1] == '\n':
        text = "ERROR: " + text
    else:
        text = "ERROR: " + text + "\n"
    if not quiet:
        stdout.write(inprogress + text)
        stdout.flush()
        inprogress = ''
    if filelog:
        filelog.write(text)
    return inst


def INFO(text):
    """
    Write an information message to stdout + log file.
    No message is printed if 'level' is below 1.
    """

    global inprogress

    if text[-1] == '\n':
        text = "INFO: " + text
    else:
        text = "INFO: " + text + "\n"
    if not quiet and level >= 1:
        stdout.write(inprogress + text)
        stdout.flush()
        inprogress = ''
    if filelog and level >= 1:
        filelog.write(text)


def DEBUG(text):
    """
    Write a debug message to log file only.
    No message is printed if 'level' is below 2.
    """

    if text[-1] == '\n':
        text = "DEBUG: " + text
    else:
        text = "DEBUG: " + text + "\n"
    if filelog and level >= 2:
        filelog.write(text)


def init(filename=None, verbose=0, progress=True, title=''):
    """
    Select 'filename' as the log file. 

    Messages will be added to the file (append mode), 'verbose' controls
    the log level and 'progress' flag the use of stdout for monitoring.
    """

    global filelog, level, quiet, inprogress

    if filename:
        filelog = open(filename, "a")
    else:
        filelog = None
    level = int(verbose)
    quiet = not progress
    inprogress = ''
    if filelog:
        title = title.strip()
        if title:
            text = "Start %s" % title
        else:
            text = "Start"
        msg = [ time.strftime("%Y.%m.%d %H.%M.%S:", time.localtime()),
                "*" * 7, text, "*" * 7 ]
        filelog.write(' '.join(msg) + '\n')


def close(title=''):
    """
    Close the log file.
    """

    global filelog

    if filelog:
        title = title.strip()
        if title:
            text = "Done %s" % title
        else:
            text = "Done"
        msg = [ time.strftime("%Y.%m.%d %H.%M.%S:", time.localtime()),
                "*" * 7, text, "*" * 7 ]
        filelog.write(' '.join(msg) + '\n')
        filelog.close()
    filelog = None


def starting(text, nb):
    """
    Start a percent progression meter.

    The number 'nb' represent 100%.
    A timer is also started.
    """

    global inprogress, progresstext, progressmax
    global progressnext, progresstimer, progresscpt

    if not quiet:
        stdout.write(inprogress + text + ' 0%')
        stdout.flush()
        inprogress = '\n'
        if nb > 0:
            progressmax = nb
        progressnext = int(progressmax/100.0)
        progresstext = '\r' + text + ' '
        progresstimer = time.time()
        progresscpt = 0


def progress(num=None):
    """
    Display loop progress, 100% is reached when 'num' is equal to 'nb'.
    """

    global inprogress, progressnext, progresscpt

    if not quiet and progressmax:
        if num is None:
            progresscpt += 1
            num = progresscpt
        if num > progressnext < progressmax:
            num = int(100.0*num/progressmax)
            stdout.write(progresstext + str(num) + '%')
            stdout.flush()
            progressnext = int((num+1)*progressmax/100.0)
            inprogress = '\n'


def ending():
    """
    Stop progression meter and display elapsed time.
    """

    global progressmax, inprogress

    progressmax = 0
    if not quiet:
        stdout.write(progresstext + '100%')
        stdout.flush()
        elapsed = time.time() - progresstimer
        stdout.write(" (%dmin%02ds)\n" % (int(elapsed/60), int(elapsed%60)))
        inprogress = ''
