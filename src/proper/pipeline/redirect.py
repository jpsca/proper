from typing import TYPE_CHECKING

from ..current import request, response

if TYPE_CHECKING:
    from proper import Response


__all__ = ("redirect",)


def redirect() -> "Response | None":
    """If a matched route is a redirect sets the header and response body
    for that redirect to happen and stop further process of the response.
    """
    route = request.matched_route
    if not route:
        return

    if route.redirect:
        params = request.matched_params or {}
        response.redirect_to(
            route.redirect.format(**params),
            status=route.redirect_status,
        )
        return response
