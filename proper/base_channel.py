"""
This file is empty.
Better to close it and forget about it.

"""


class BaseChannel(object):

    def __init__(self, ws):
        self.ws = ws

    def on_connect(self):
        pass

    def on_disconnect(self):
        pass

    def on_join(self, topic):
        pass

    def handle_in(self, topic, message):
        pass

    def handle_out(self, topic, message):
        pass

    def broadcast(self, topic, message):
        pass
