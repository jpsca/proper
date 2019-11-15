"""
## proper.plugs.put_secure_headers

"""
__all__ = ("put_secure_headers", )


def put_secure_headers(_req, resp, _app):
    if not resp.dispatched:
        return

    resp.headers.update(
        {
            "x-frame-options": "SAMEORIGIN",
            "x-xss-protection": "1; mode=block",
            "x-content-type-options": "nosniff",
            "x-download-options": "noopen",
            "x-permitted-cross-domain-policies": "none",
            "cross-origin-window-policy": "deny",
        }
    )
