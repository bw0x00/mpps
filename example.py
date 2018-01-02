#!/bin/env python3

"""
$LICENSE
"""


from mpps import pluginmanager
import sys
import time

import globaldef

CONF = "./conf.d"
PLUGINS = "./plugins"


class MsgHandler:

    def __init__(self):
        pass

    def process(self, msg):
        self.print_msg(msg)

    def print_msg(self, msg):
        outln = ""
        try:
            outln = ''.join(
                (msg.get_issuer(), "::", msg.get_longstatus(), "> "))
        except KeyError:
            print(''.join(("> ", "Unknown Message Type ",
                           msg.get_status(), " from Plugin ",
                           msg.get_issuer())))
        finally:
            if msg.get_status() != "data":
                for line in msg.get_content().split('\n'):
                    print(outln + line)
            elif globaldef.debug:
                print(outln + str(msg.get_content()))


def collect():
    m_handler = MsgHandler()
    p_handler = pluginmanager.PluginManager(PLUGINS, CONF)
    p_list = p_handler.get_plugins()
    print("Loading Plugins:")
    try:
        for i in p_list:
            print("> " + i)

            p_handler.load_plugin(i)
            p_handler.run_plugin(i)

        print("\n")

        print("# Example 1: Running all plugins in a loop\n")
        while p_handler.get_running_plugins():
            # try:
            #    msg = p_handler.next_msg()
            #    m_handler.process(msg)
            #    if msg.get_status() == "fin":
            #        p_handler.stop_plugin(msg.get_issuer())
            # except Empty:
            #    pass
            fin = []
            for p in p_handler:
                for msg in p:
                    if msg.get_status() == "fin":
                        fin.append(p)
                    m_handler.process(msg)
            for p in fin:
                p_handler.stop_plugin(p)
            time.sleep(0.1)

        sys.exit(0)
        print("""# Example 2: One specified Plugin with an callback
              eventhandler (threaded)""")
        print("Available Plugins: \n" +
              "\n> ".join(p_handler.get_loaded_plugins()))
        p = p_handler.get_loaded_plugins()[0]
        print("\nRunning Plugin " + str(p) + "\n\n")
        p_handler.add_msg_handler(m_handler.process, p)
        p_handler.run_plugin(p)

    except KeyboardInterrupt:
        print("\n> CTRL+C detected")
    except ImportError as e:
        print(e)
    except Exception as e:
        print(e)
    finally:
        del p_handler
        print("\n> Exiting...")
        sys.exit(0)


def main():
    print("Example Usage of the Multiprocessing Plugin System (MPPS)\n")
    collect()

if __name__ == "__main__":
    main()
