import typing as t

import itsdangerous

from . import status


class BadSecretKey(Exception):
    pass


class MissingRouteParameter(Exception):
    def __init__(self, name: str, path: str) -> None:
        msg = f"missing value for {name} in {path}"
        super().__init__(msg)


class BadRoutePlaceholder(Exception):
    def __init__(self, name: str, path: str, rx: str) -> None:
        msg = f"placeholder {name} doesn't have the expected format <{rx}> in {path}"
        super().__init__(msg)


class DuplicatedRoutePlaceholder(Exception):
    def __init__(self, name: str, path: str) -> None:
        msg = f"placeholder {name} declared more than once in {path}"
        super().__init__(msg)


class BadRouteFormat(Exception):
    pass


class RouteNotFound(Exception):
    pass


class WrongHashAlgorithm(Exception):
    pass


class BadSignature(itsdangerous.BadSignature):
    def __init__(self, message: str = "Bad signtaure", payload: t.Any = None):
        super().__init__(message, payload)


class TranslationsNotFound(Exception):
    def __init__(self, locale: str) -> None:
        if "_" in locale:
            lang = locale.split("_")[0]
            msg = f"No translations found for the '{locale}' or '{lang}' locales"
        else:
            msg = f"No translations found for the '{locale}' locale"
        super().__init__(msg)


class HTTPError(Exception):
    """A generic HTTP error.

    Arguments are:

    - msg (str):
        Description of the error.

    - status (str):
        HTTP status line, e.g. '200 OK' or '725 It works on my machine'.

    - **headers (dict):
        Optional headers to attach to the response

    """

    __slots__ = ("msg", "status", "headers")

    def __init__(
        self,
        msg: str = "",
        status: str = "500 Error",
        **headers: list[str],
    ):
        self.msg = msg
        self.status = getattr(self, "status", status)
        self.headers = headers

    def __str__(self):
        return self.msg

    def __repr__(self):
        return f'{self.__class__.__name__}("{self.msg}")'

    @property
    def status_code(self) -> int:
        return int(self.status.split(" ", 1)[0])

    @property
    def description(self) -> str:
        return self.__doc__ or ""


class BadRequest(HTTPError):
    """400 Bad Request.

    The server cannot or will not process the request due to something
    that is perceived to be a client error (e.g., malformed request
    syntax, invalid request message framing, or deceptive request
    routing).
    """

    status = status.bad_request


class InvalidHeader(BadRequest):
    """400 Bad Request.

    One of the headers in the request is invalid.
    """


class ClientDisconnected(BadRequest):
    """400 Bad Request.

    The request was interrupted.
    """


class MultipartError(BadRequest):
    """400 Bad Request.

    The form data cannot be parsed..
    """


class MissingHeader(BadRequest):
    """400 Bad Request.

    One of the headers in the request is missing.
    """


class BadRequestKeyError(BadRequest, KeyError):
    """An exception that is used to signal both a KeyError and a
    BadRequest.
    """

    def __init__(self, key: str | None = None, *args: t.Any, **kwargs: t.Any):
        super().__init__(*args, **kwargs)

        if key is None:
            KeyError.__init__(self)
        else:
            KeyError.__init__(self, key)


class Unauthorized(HTTPError):
    """401 Unauthorized.

    The request has not been applied because it lacks valid
    authentication credentials for the target resource.

    The server generating a 401 response MUST send a WWW-Authenticate
    header field containing at least one challenge applicable to the
    target resource.

    If the request included authentication credentials, then the 401
    response indicates that authorization has been refused for those
    credentials. The user agent MAY repeat the request with a new or
    replaced Authorization header field. If the 401 response contains
    the same challenge as the prior response, and the user agent has
    already attempted authentication at least once, then the user agent
    SHOULD present the enclosed representation to the user, since it
    usually contains relevant diagnostic information.
    """

    status = status.unauthorized


class Forbidden(HTTPError):
    """403 Forbidden.

    The server understood the request but refuses to authorize it.
    A server that wishes to make public why the request has been
    forbidden can describe that reason in the response payload (if any).

    If authentication credentials were provided in the request, the
    server considers them insufficient to grant access. The client
    SHOULD NOT automatically repeat the request with the same
    credentials. The client MAY repeat the request with new or different
    credentials. However, a request might be forbidden for reasons
    unrelated to the credentials.

    An server that wishes to hide the existence of a forbidden target
    resource MAY instead respond with a status code of '404 Not Found'.
    """

    status = status.forbidden


class MissingCSRFToken(Forbidden):
    """403 Forbidden.

    We couldn't find a CSRF token in the request.
    """


class InvalidCSRFToken(Forbidden):
    """403 Forbidden.

    The CSRF token was found but didn't match with the one stored in the session.
    """


class NotFound(HTTPError):
    """404 Not Found.

    The origin server did not find a current representation for the
    target resource or is not willing to disclose that one exists.

    A 404 status code does not indicate whether this lack of
    representation is temporary or permanent; the 410 Gone status code
    is preferred over 404 if the origin server knows that the condition
    is likely to be permanent.
    """

    status = status.not_found


class MatchNotFound(NotFound):
    """404 Not Found.

    We couldn't found a matching route for the requested URL.

    This exception exists to helping development by differentiating routing
    errors from other 404 Not Found exceptions caused by unexisting
    database records and such.
    """


class MethodNotAllowed(HTTPError):
    """405 Method Not Allowed.
    The method received in the request-line is known by the origin
    server but not supported by the target resource.

    The origin server MUST generate an Allow header field in a 405
    response containing a list of the target resource's currently
    supported methods.
    """

    status = status.method_not_allowed

    def __init__(self, msg, allowed, **headers):
        headers.setdefault("Allow", ", ".join(allowed))
        super().__init__(msg, status=self.status, **headers)


class NotAcceptable(HTTPError):
    """406 Not Acceptable.

    The target resource does not have a current representation that
    would be acceptable to the user agent, according to the proactive
    negotiation header fields received in the request, and the server
    is unwilling to supply a default representation.
    """

    status = status.not_acceptable


class Conflict(HTTPError):
    """409 Conflict.

    The request could not be completed due to a conflict with the
    current state of the target resource. This code is used in
    situations where the user might be able to resolve the conflict and
    resubmit the request.

    The server SHOULD generate a payload that includes enough
    information for a user to recognize the source of the conflict.

    Conflicts are most likely to occur in response to a PUT request. For
    example, if versioning were being used and the representation being
    PUT included changes to a resource that conflict with those made by
    an earlier (third-party) request, the origin server might use a 409
    response to indicate that it can't complete the request. In this
    case, the response representation would likely contain information
    useful for merging the differences based on the revision history.
    """

    status = status.conflict


class Gone(HTTPError):
    """410 Gone.

    The target resource is no longer available at the origin server and
    this condition is likely to be permanent.

    If the origin server does not know, or has no facility to determine,
    whether or not the condition is permanent, the status code 404 Not
    Found ought to be used instead.

    The 410 response is primarily intended to assist the task of web
    maintenance by notifying the recipient that the resource is
    intentionally unavailable and that the server owners desire that
    remote links to that resource be removed.
    """

    status = status.gone


class LengthRequired(HTTPError):
    """411 Length Required.

    The server refuses to accept the request without a defined Content-
    Length.
    """

    status = status.length_required


class PreconditionFailed(HTTPError):
    """412 Precondition Failed.

    One or more conditions given in the request header fields evaluated
    to false when tested on the server.

    This response code allows the client to place preconditions on the
    current resource state (its current representations and metadata)
    and, thus, prevent the request method from being applied if the
    target resource is in an unexpected state.
    """

    status = status.precondition_failed


class RequestEntityTooLarge(HTTPError):
    """413 Request Entity Too Large.

    The server is refusing to process a request because the request
    payload is larger than the server is willing or able to process.
    """

    status = status.request_entity_too_large


class UriTooLong(HTTPError):
    """414 URI Too Long.

    The server is refusing to service the request because the request-
    target is longer than the server is willing to interpret.

    This rare condition is only likely to occur from a client error
    or an attack attempt by a client.
    """

    status = status.request_uri_too_long


class UnsupportedMediaType(HTTPError):
    """415 Unsupported Media Type.

    The origin server is refusing to service the request because the
    payload is in a format not supported by this method on the target
    resource.

    The format problem might be due to the request's indicated Content-
    Type or Content-Encoding, or as a result of inspecting the data
    directly.
    """

    status = status.unsupported_media_type


class RangeNotSatisfiable(HTTPError):
    """416 Range Not Satisfiable.

    The server cannot serve the requested ranges. The most likely reason is
    that the document doesn't contain such ranges, or that the Range header
    value, though syntactically correct, doesn't make sense.

    The format problem might be due to the request's indicated Content-
    Type or Content-Encoding, or as a result of inspecting the data
    directly.

    The 416 response message contains a Content-Range with
    the current length of the resource, that you need to provide
    to raise thie exception.
    """

    status = status.range_not_satisfiable

    def __init__(self, msg, length: int | str = "*", **headers):
        headers.setdefault("Content-Range", f"bytes */{length}")
        super().__init__(msg, status=self.status, **headers)


class UnprocessableEntity(HTTPError):
    """422 Unprocessable Entity.

    The server understands the content type of the request entity (hence
    a 415 Unsupported Media Type status code is inappropriate), and the
    syntax of the request entity is correct (thus a 400 Bad Request
    status code is inappropriate) but was unable to process the
    contained instructions.
    """

    status = status.unprocessable_entity


class FailedDependency(HTTPError):
    """424 Failed Dependency.

    The 424 (Failed Dependency) status code means that the method could
    not be performed on the resource because the requested action
    depended on another action and that action failed.
    """

    status = status.failed_dependency


class PreconditionRequired(HTTPError):
    """428 Precondition Required.

    The 428 status code indicates that the origin server requires the
    request to be conditional.

    Its typical use is to avoid the 'lost update' problem, where a client
    GETs a resource's state, modifies it, and PUTs it back to the server,
    when meanwhile a third party has modified the state on the server,
    leading to a conflict.  By requiring requests to be conditional, the
    server can assure that clients are working with the correct copies.
    """

    status = status.precondition_required


class TooManyRequests(HTTPError):
    """429 Too Many Requests.

    The user has sent too many requests in a given amount of time ('rate
    limiting').
    The response representations SHOULD include details explaining the
    condition, and MAY include a Retry-After header indicating how long
    to wait before making a new request.
    """

    status = status.too_many_requests


class UnavailableForLegalReasons(HTTPError):
    """451 Unavailable For Legal Reasons.

    The server is denying access to the resource as a consequence of a
    legal demand.

    Responses using this status code SHOULD include an explanation, in
    the response body, of the details of the legal demand: the party
    making it, the applicable legislation or regulation, and what
    classes of person and resource it applies to.
    """

    status = status.unavailable_for_legal_reasons


class InternalServerError(HTTPError):
    """500 Internal Server Error.

    The server encountered an unexpected condition that prevented it
    from fulfilling the request.
    """

    status = status.internal_server_error


ServerError = InternalServerError
Error = InternalServerError


class NotImplemented(HTTPError):
    """501 Not Implemented.

    The 501 (Not Implemented) status code indicates that the server does
    not support the functionality required to fulfill the request.  This
    is the appropriate response when the server does not recognize the
    request method and is not capable of supporting it for any resource.
    """

    status = status.not_implemented


class InsufficientStorage(HTTPError):
    """507 Insufficient Storage.

    The 507 (Insufficient Storage) status code means the method could not
    be performed on the resource because the server is unable to store
    the representation needed to successfully complete the request. This
    condition is considered to be temporary. If the request that
    received this status code was the result of a user action, the
    request MUST NOT be repeated until it is requested by a separate user
    action.
    """

    status = status.insufficient_storage


class NetworkAuthenticationRequired(HTTPError):
    """511 Network Authentication Required.

    The 511 status code indicates that the client needs to authenticate
    to gain network access.
    """

    status = status.network_authentication_required
