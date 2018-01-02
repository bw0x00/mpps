#!/bin/env python3

"""
$LICENSE
"""

import globaldef

from mpps.plugin import PluginClass

config = {}


def init(com, config, name):
    return ExamplePlugin(com, config, name)


class ExamplePlugin(PluginClass):

    def __init__(self, com, config, name):
        super().__init__(com, config, name)

    def __del__(self):
        super().__del__()

    def run(self):
        self._send("warn", "Example Plugin 2 Running")

        if globaldef.debug:
            self._send("notify", "Debug Test")
            self._send("err", "Debug Error Test")

        self._send("data", "Example Data")
        self._send("fin", "")

if __name__ == "__main__":
    pass
