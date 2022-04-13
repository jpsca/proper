from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from proper import App, Request, Response


__all__ = ("redirect",)


def redirect(request: "Request", response: "Response", app: "App") -> None:
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
