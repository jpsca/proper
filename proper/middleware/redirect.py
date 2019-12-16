"""
## proper.middleware.redirect

"""
__all__ = ("redirect", )


def redirect(req, resp, _app):
    """If a matched route is a redirect, sets the header and response body for
    that redirect to happens."""
    if resp.dispatched:
        return

    route = req.matched_route
    if route and route.redirect:
        resp.dispatched = True
        resp.redirect_to(
            route.redirect.format(**req.matched_params),
            status_code=route.redirect_status_code,
        )
        resp.stop = True
