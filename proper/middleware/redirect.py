__all__ = ("redirect",)


def redirect(request, response, app):
    """If a matched route is a redirect sets the header and response body
    for that redirect to happen and stop further process of the response.
    """
    route = request.matched_route
    if not route:
        return

    if route.redirect:
        response.redirect_to(
            route.redirect.format(**request.matched_params),
            status_code=route.redirect_status_code,
        )
        response.stop = True
        return
