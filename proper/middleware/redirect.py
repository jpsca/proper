"""
## proper.middleware.redirect

"""
__all__ = ("redirect",)


def redirect(req, resp, _app):
    """If a matched route is a redirect: sets the header and response body
    for that redirect to happen. If it is a forward does noting.
    In both cases it stop further process of the response.
    """
    if resp.dispatched:
        return

    route = req.matched_route
    if not route:
        return

    if route.forward_to:
        resp.stop = True
        return

    if route.redirect:
        resp.redirect_to(
            route.redirect.format(**req.matched_params),
            status_code=route.redirect_status_code,
        )
        resp.stop = True
        return
