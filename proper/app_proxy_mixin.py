"""
## proper.app_proxy_mixin

"""


class AppProxyMixin(object):
    @property
    def debug(self):
        return self.config.get("debug", False)

    @property
    def routes(self):
        """Proxy for `~router.routes`."""
        return self.router._routes

    @routes.setter
    def routes(self, values):
        """Proxy for `~router.routes`."""
        self.router.routes = values

    @property
    def channels(self):  # pragma: no cover
        """Proxy for `~router.channels`."""
        return self.router._channels

    @channels.setter
    def channels(self, values):  # pragma: no cover
        """Proxy for `~router.channels`."""
        self.router.channels = values

    def url_for(self, name, *, _external=False, _anchor=None, **kwargs):
        """Proxy for `~router.url_for()`."""
        return self.router.url_for(name, _external=_external, _anchor=_anchor, **kwargs)
