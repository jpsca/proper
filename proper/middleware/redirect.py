__all__ = ("redirect",)


def redirect(req, resp, app):
    """If a matched route is a redirect sets the header and response body
    for that redirect to happen and stop further process of the response.
    """
    route = req.matched_route
    if not route:
        return

    if route.redirect:
        resp.redirect_to(
            route.redirect.format(**req.matched_params),
            status_code=route.redirect_status_code,
        )
        resp.stop = True
        return
