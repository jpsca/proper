import proper.server


class AppServer:
    def run_server(self, host=None, port=None):
        host = self.config.host if host is None else host
        port = self.config.port if port is None else port
        try:
            proper.server.run(self, host, port)
        except KeyboardInterrupt:
            print("Goodbye!\n")
