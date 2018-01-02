#!/bin/env python3
"""
$LICENSE

This module is providing a simple plugin infrastructure.
The plugins are created as separated processes. For the communicaton,
multiprocessing.Queue is used.

$VERSION

"""

import os
import json
import time

from queue import Empty


class MsgClass:
    """
    Class for Messages to use for main process <-> plugin communication.
    This class includes some validations.
    """
    _status = ""
    _content = ""
    _issuer = ""
    _longstatus = None

    def __init__(self, status="", content="", issuer=""):
        self._status = status
        self._content = content
        self._issuer = issuer
        self._longstatus = {"err": "Error", "notify": "Notification",
                            "data": "Data", "fin": "Finished",
                            "warn": "Warning", "term": "Terminated"}

    def empty(self):
        """ Clears the content of the message """
        self._status = ""
        self._content = ""

    def set_status(self, stat):
        """ Sets the message status. Only predefined states contained in
        self._longstatus are accepted """
        if stat in self._longstatus:
            self._status = stat
        else:
            raise ValueError(
                "Value '" + stat + "' is not a valid Msg Status\n")

    def set_content(self, content):
        """ Sets the message content """
        self._content = content

    def get_longstatus(self):
        return self._longstatus[self._status]

    def get_issuer(self):
        """ Name of the msg sender. In case of MPPS, this should be the
        unique plugin name. """
        return self._issuer

    def get_content(self):
        return self._content

    def get_status(self):
        return self._status

    def copy(self):
        return MsgClass(self._status, self._content, self._issuer)


class PluginClass:
    """
    Super Class for plugins.
    This class is providing all required functionality for
    the main process <-> plugin communcation.

    __del__ and __init__ must be called in order to initialize
    everything. Otherwise many build-in helper methods of PluginClass>
    cannot be used.
    """
    _com = None
    _msg = None
    _config = None
    _name = None

    def __init__(self, com, config, name):
        """
        - config must be the path to the config containing JSON and will be
        automatically parsed and made available as the dictionary self._config
        - name is the string which is used to identify this plugin in the
        - PluginManager. This will be stored in self._name.
        - com is the queue which connects the plugin to the
        PluginManager. It will be automatically used by self._send.
        """
        self._name = name
        self._com = com
        self._msg = MsgClass(issuer=name)
        self._load_config(config)
        self._send("notify", "Initialized")

    def __del__(self):
        self._com = None

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return self._com.get_nowait()
        except Empty:
            empty = True

        if empty:
            raise StopIteration

    def __str__(self):
        return self._name

    def _load_config(self, path):
        conf_path = os.path.join(path, self._name + ".conf")
        try:
            conf_file = open(conf_path, "r")
            conf_str = conf_file.read()
            self._config = json.loads(conf_str)
        except IOError:
            self._config = ()
            self._send(stat="warn",
                       content="Unable to open config file: '"
                       + conf_path + "'")

    def _send(self, stat, content=""):
        """ Calling the message self._send sends object of type MsgClass
        through the queue stored at self._com to the PluginManager.
        """
        try:
            self._msg.set_status(stat)
            self._msg.set_content(content)
        except ValueError as e:
            self._msg = MsgClass(
                issuer=self._name, status="err", content=str(e))
        self._com.put(self._msg.copy())
        self._msg.empty()

    def send(self, stat, content=""):
        """ Calling the message self._send sends object of type MsgClass
        through the queue stored at self._com to the PluginManager.
        """
        self._send(stat, content)

    def get_com(self):
        """ Returns the Queue object providing the connection to the
        PluginManager """
        return self._com

    def run(self):
        time.sleep(0.1)


if __name__ == "__main__":
    pass
