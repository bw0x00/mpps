#!/bin/env python3

"""
$LICENSE
"""


from mpps import pluginmanager
from queue import Empty
import sys
import globaldef

CONF = "./conf.d"
PLUGINS = "./plugins"


class MsgHandler:
    _p_handler = None

    def __init__(self, p):
        self._p_handler = p

    def process(self, msg):
        self.print_msg(msg)
        if msg.get_status() == "fin":
            self._p_handler.stop_plugin(msg.get_issuer())

    def print_msg(self, msg):
        outln = ""
        try:
            outln = ''.join(
                (msg.get_issuer(), "::", msg.get_longstatus(), "> "))
        except KeyError:
            print(''.join(("> ", "Unknown Message Type ",
                           msg.get_status(), " from Plugin ",
                           msg.get_issuer())))
        except Exception as e:
            print(e)

        if msg.get_status() != "data":
            for line in msg.get_content().split('\n'):
                print(outln + line)
        elif globaldef.debug:
            print(outln + str(msg.get_content()))


def collect():
    p_handler = pluginmanager.PluginManager(PLUGINS, CONF)
    m_handler = MsgHandler(p_handler)
    p_list = p_handler.get_plugins()
    print("Loading Plugins:")
    try:
        for i in p_list:
            print("LOADED> " + i)

            p_handler.load_plugin(i)
            print("\n")

            if not i == "examplePlugin":
                p_handler.add_callback(m_handler.process, i)
            p_handler.run_plugin(i)

        # Shut them down
        p_handler.shutdown_callbacks()

        print("\nCallbacks terminated\n")
        print("Remaining Non-callback Messages:")
        while p_handler.get_running_plugins():
            try:
                msg = p_handler.next_msg()
                m_handler.print_msg(msg)
                if msg.get_status() == "fin":
                    p_handler.stop_plugin(msg.get_issuer())
            except Empty:
                pass

    except KeyboardInterrupt:
        print("\n> CTRL+C detected")
    except ImportError as e:
        print(e)

    del p_handler
    print("\n> Exiting...")
    sys.exit(0)


def main():
    print("Example Usage of the Multiprocessing Plugin System (MPPS)\n")
    collect()

if __name__ == "__main__":
    main()
