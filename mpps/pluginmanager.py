#!/bin/env python3
"""
$LICENSE

This module is providing a simple plugin infrastructure.
The plugins are created as separated processes. For the communicaton,
multiprocessing.Queue is used.

$VERSION

"""

import os
import imp
import multiprocessing
import threading
import time

from queue import Empty
from mpps.plugin import PluginClass
from mpps.plugin import MsgClass


class PluginManager(threading.Thread):
    """
    Plugin Manager to start and manage multiprocessed background plugins.
    Communicaton between starter and plugin manager is implemented with
    multiprocessing.Queues. Access to queues is encapsulated in the function
    'next_msg(plugin=None)'.
    """
    _config = None
    _path = None
    _MAINMODULE = "__init__"

    _plugins = None
    _loaded_plugins = None
    _running_plugins = None
    _syncmanagers = None
    _callbacks = None
    _running = None
    _fin = None

# ===== START OF LOCK CLASS

    class GetLock:
        """
        Locks datastructures of a PluginManger object in order to provide
        multithreading support.
        """
        _lock = threading.Lock()
        _lock_loaded = threading.Lock()
        _lock_running = threading.Lock()
        _lock_callback = threading.Lock()

        def __init__(self, target=False):
            self._target = target

        @classmethod
        def acquire(cls, target):
            if not target:
                cls._lock_loaded.acquire()
                cls._lock_running.acquire()
                cls._lock_callback.acquire()
            elif target == "loaded_plugins":
                cls._lock_loaded.acquire()
            elif target == "running_plugins":
                cls._lock_running.acquire()
            elif target == "callbacks":
                cls._lock_callback.acquire()
            else:
                raise ValueError("Lock target '" + target + "' is not defined")

        @classmethod
        def release(cls, target):
            if not target:
                cls._lock_running.release()
                cls._lock_loaded.release()
                cls._lock_callback.release()
            elif target == "running_plugins":
                cls._lock_running.release()
            elif target == "loaded_plugins":
                cls._lock_loaded.release()
            elif target == "callbacks":
                cls._lock_callback.release()
            else:
                raise ValueError("Lock target '" + target + "' is not defined")

        def __call__(self, func):
            def _with_getlock(*args, **kwargs):
                self.acquire(self._target)
                try:
                    return func(*args, **kwargs)
                except:
                    raise
                finally:
                    self.release(self._target)
            return _with_getlock

# ===== END OF LOCK CLASS

    def __init__(self, pluginpath, configpath):
        self._path = pluginpath
        self._config = configpath
        self._loaded_plugins = {}
        self._running_plugins = {}
        self._callbacks = {}
        self._syncmanagers = {}
        self._plugins = {}
        self._find_plugins()
        self._running = False
        self._fin = False
        super().__init__()
        self.daemon = True

    def __del__(self):
        self._fin = True
        if self._running_plugins is not None:
            for p in list(self._running_plugins.keys()):
                self.stop_plugin(p)
        if self._callbacks is not None:
            for p in list(self._callbacks.keys()):
                self.end_msg_callback(p)
        if self._plugins is not None:
            for p in self._plugins:
                self._plugins[p][0].close()
        if self._running:
            self.join()
        if self._syncmanagers is not None:
            for p in self._syncmanagers:
                self._syncmanagers[p].shutdown()

    def __iter__(self):
        return [self._running_plugins[p][1]
                for p in self._running_plugins.keys()].__iter__()

    def get_plugins(self):
        """ Returns a list containing all plugins """
        return list(self._plugins.keys())

    def get_loaded_plugins(self):
        """ Returns a list containing loaded plugins """
        return list(self._loaded_plugins.keys())

    def get_running_plugins(self):
        """ Returns a list containing all running plugins """
        return list(self._running_plugins.keys())

    def get_active_callbacks(self):
        """ Returns a list containing all registered callback handlers """
        return list(self._callbacks.keys())

    def _find_plugins(self):
        """ Scans configured folder for plugins.
        Original Plugin System taken from MiJyn, modified by bw0x00
        http://lkubuntu.wordpress.com/2012/10/02/writing-a-python-plugin-api/
        """
        possibleplugins = os.listdir(self._path)
        for i in possibleplugins:
            location = os.path.join(self._path, i)
            if not os.path.isdir(location) or \
               not self._MAINMODULE + ".py" in os.listdir(location):
                    continue
            self._plugins[i] = imp.find_module(self._MAINMODULE, [location])

    def run(self):
        """ Worker loop for callback worker Thread """

        class Handler(threading.Thread):
            """ Inner Class used to set up the Thread to process the message
            """
            def __init__(self, handler, msg):
                self.handler = handler
                self.msg = msg
                super().__init__()
                self.daemon = True

            def run(self):
                self.handler(self.msg)

        while not self._fin:
            delay = 0.1
            cbs = self._callbacks.copy()
            if len(cbs) != 0:
                for plugin in cbs.keys():
                    try:
                        m = self.next_msg(plugin, True)
                        t = Handler(msg=m, handler=cbs[plugin])
                        t.start()
                        delay = 0
                    except Empty:
                        pass
                    except KeyError:
                        pass
            time.sleep(delay)
        self._running = False

    @GetLock("callbacks")
    def end_callback(self, plugin_in):
        """ Removes callback handler. """
        plugin = str(plugin_in)
        if plugin in self._callbacks:
            self._callbacks.pop(plugin)
        else:
            raise KeyError("No handler registered for '" + plugin + "'.")

    def shutdown_callbacks(self):
        """ Terminates removes all registered callback handler and terminates
        the worker thread
        """
        self._fin = True
        self._running = False
        self.join()
        callbacks = list(self._callbacks.keys())
        for c in callbacks:
            self.end_callback(c)
        self._callbacks = {}

    @GetLock("callbacks")
    def add_callback(self, handler, plugin_in):
        """ Adds message handlers for incoming messages.
        Parameter 'plugin' defines the plugin for which the handler should
        be registered.
        Handlers can only be added for loaded plugins. Furthermore, they are
        removed if the plugin is stopped or finishes.
        """
        if self._fin:
            raise Exception("Callback worker thread already ended.")
        plugin = str(plugin_in)
        if not self._running:
            self.start()                    # starts worker for async callbacks
            self._running = True
        if plugin in self._loaded_plugins and hasattr(handler, '__call__'):
            self._callbacks[plugin] = handler
        elif plugin not in self._plugins:
            raise KeyError("Plugin '" + plugin + "' is not available")
        elif plugin not in self._loaded_plugins:
            raise KeyError("Plugin '" + plugin + "' is not loaded")
        else:
            raise TypeError("First parameter 'handler' has to be a function")

    @GetLock("loaded_plugins")
    def load_plugin(self, plugin):
        """
        Loads plugin with the name passed in parameter 'plugin' if plugin is
        available.
        If no plugin with given name was found, an exception of type KeyError
        will be risen.

        Plugin System from MiJyn, modified by bw0x00
        http://lkubuntu.wordpress.com/2012/10/02/writing-a-python-plugin-api/
        """
        if plugin in self._plugins:
            self._loaded_plugins[plugin] = imp.load_module(
                plugin, *self._plugins[plugin])
            self._syncmanagers[plugin] = multiprocessing.Manager()
        else:
            raise KeyError("Plugin '" + plugin + "' does not exist.\n")

    @GetLock("running_plugins")
    def run_plugin(self, plugin_in):
        """
        Runs a previously loaded plugin. Plugin has to be instance of
        'PluginClass' or of other derived class.

        Raises TypeError if plugin to load is not instance of 'PluginClass'.
        Raises KeyError if plugin was not loaded or is not available
        """
        plugin = str(plugin_in)
        if plugin in self._loaded_plugins:
            com = self._syncmanagers[plugin].Queue()
            p = self._loaded_plugins[plugin].init(com, self._config, plugin)
            if not isinstance(p, PluginClass):
                raise TypeError(
                    "'" + plugin + "' is not instance of 'PluginClass'")
            mp = multiprocessing.Process(target=p.run)
            mp.start()
            self._running_plugins[plugin] = (mp, p)
        elif plugin in self._plugins:
            raise KeyError("Plugin '" + plugin + "' is not loaded.")
        else:
            self._lock.release()
            raise KeyError("Plugin '" + plugin + "' does not exist.")

    @GetLock("running_plugins")
    def stop_plugin(self, plugin_in):
        """
        Stops the passed plugin and closes the corresponding Queue.
        """
        plugin = str(plugin_in)
        if plugin in self._running_plugins:
            if plugin in self._callbacks:
                self.end_callback(plugin)
            self._running_plugins[plugin][0].terminate()
            self._running_plugins.pop(plugin)
        elif plugin in self._loaded_plugins:
            raise KeyError("Plugin '" + plugin + "' is not running.")
        elif plugin in self._plugins:
            raise KeyError("Plugin '" + plugin + "' is not loaded.")
        else:
            raise KeyError("Plugin '" + plugin + "' does not exist.")

    @GetLock("running_plugins")
    def next_msg(self, plugin=None, callback=False):
        """
        Trying to read the next message for provided plugin. If plugin is not
        specified, all running plugins are iterated and the first msg found is
        passed back to caller.
        If no message is found, queue.Empty is raised.
        Returned messages are instances of 'MsgClass'.
        """
        msg = None
        if plugin in self._running_plugins:
            if plugin not in self._callbacks or \
               (plugin in self._callbacks and callback):
                msg = self._running_plugins[plugin][1].get_com().get_nowait()
        elif plugin is None:
            for p in self._running_plugins:
                if p not in self._callbacks:
                    try:
                        msg = self._running_plugins[p][1].get_com().\
                            get_nowait()
                        break
                    except Empty:
                        pass
        elif plugin in self._loaded_plugins:
            raise KeyError("Plugin '" + plugin + "' is not running.")
        elif plugin in self._plugins:
            raise KeyError("Plugin '" + plugin + "' is not loaded.")
        else:
            raise KeyError("Plugin '" + plugin + "' does not exist.")

        if msg is None:
            raise Empty  # raise Empty if no plugin has a message
        elif not isinstance(msg, MsgClass):
            raise TypeError("'" + str(msg) + "' is not instance of 'MsgClass'")

        return msg


if __name__ == "__main__":
    pass
