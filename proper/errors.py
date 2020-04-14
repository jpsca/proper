from . import status


class HTTPError(Exception):
    """A generic HTTP error.

    Arguments are:

        msg (str):
            Description of the error.

        status (str):
            HTTP status line, e.g. '200 OK' or '725 It works on my machine'.

        **headers (dict):
            Optional headers to attach to the response

    """

    __slots__ = ("msg", "status_code", "headers")

    def __init__(self, msg="", status_code=None, **headers):
        self.msg = msg
        self.status_code = getattr(self, "status_code", status_code)
        self.headers = headers

    def __str__(self):
        return self.msg

    def __repr__(self):
        return f'{self.__class__.__name__}("{self.msg}")'


class BadRequest(HTTPError):
    """400 Bad Request.

    The server cannot or will not process the request due to something
    that is perceived to be a client error (e.g., malformed request
    syntax, invalid request message framing, or deceptive request
    routing).
    """

    status_code = status.bad_request


class InvalidHeader(BadRequest):
    """400 Bad Request.

    One of the headers in the request is invalid.
    """


class ClientDisconnected(BadRequest):
    """400 Bad Request.

    The request was interrupted.
    """


class MissingHeader(BadRequest):
    """400 Bad Request.

    One of the headers in the request is missing.
    """


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

    status_code = status.unauthorized


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

    status_code = status.forbidden


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

    status_code = status.not_found


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

    status_code = status.method_not_allowed

    def __init__(self, msg, allowed, **headers):
        headers.setdefault("Allow", ", ".join(allowed))
        super().__init__(msg, status_code=self.status_code, **headers)


class NotAcceptable(HTTPError):
    """406 Not Acceptable.

    The target resource does not have a current representation that
    would be acceptable to the user agent, according to the proactive
    negotiation header fields received in the request, and the server
    is unwilling to supply a default representation.
    """

    status_code = status.not_acceptable


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

    status_code = status.conflict


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

    status_code = status.gone


class LengthRequired(HTTPError):
    """411 Length Required.

    The server refuses to accept the request without a defined Content-
    Length.
    """

    status_code = status.length_required


class PreconditionFailed(HTTPError):
    """412 Precondition Failed.

    One or more conditions given in the request header fields evaluated
    to false when tested on the server.

    This response code allows the client to place preconditions on the
    current resource state (its current representations and metadata)
    and, thus, prevent the request method from being applied if the
    target resource is in an unexpected state.
    """

    status_code = status.precondition_failed


class RequestEntityTooLarge(HTTPError):
    """413 Request Entity Too Large.

    The server is refusing to process a request because the request
    payload is larger than the server is willing or able to process.
    """

    status_code = status.request_entity_too_large


class UriTooLong(HTTPError):
    """414 URI Too Long.

    The server is refusing to service the request because the request-
    target is longer than the server is willing to interpret.

    This rare condition is only likely to occur from a client error
    or an attack attempt by a client.
    """

    status_code = status.request_uri_too_long


class UnsupportedMediaType(HTTPError):
    """415 Unsupported Media Type.

    The origin server is refusing to service the request because the
    payload is in a format not supported by this method on the target
    resource.

    The format problem might be due to the request's indicated Content-
    Type or Content-Encoding, or as a result of inspecting the data
    directly.
    """

    status_code = status.unsupported_media_type


class UnprocessableEntity(HTTPError):
    """422 Unprocessable Entity.

    The server understands the content type of the request entity (hence
    a 415 Unsupported Media Type status code is inappropriate), and the
    syntax of the request entity is correct (thus a 400 Bad Request
    status code is inappropriate) but was unable to process the
    contained instructions.
    """

    status_code = status.unprocessable_entity


class FailedDependency(HTTPError):
    """424 Failed Dependency.

    The 424 (Failed Dependency) status code means that the method could
    not be performed on the resource because the requested action
    depended on another action and that action failed.
    """

    status_code = status.failed_dependency


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

    status_code = status.precondition_required


class TooManyRequests(HTTPError):
    """429 Too Many Requests.

    The user has sent too many requests in a given amount of time ('rate
    limiting').
    The response representations SHOULD include details explaining the
    condition, and MAY include a Retry-After header indicating how long
    to wait before making a new request.
    """

    status_code = status.too_many_requests


class UnavailableForLegalReasons(HTTPError):
    """451 Unavailable For Legal Reasons.

    The server is denying access to the resource as a consequence of a
    legal demand.

    Responses using this status code SHOULD include an explanation, in
    the response body, of the details of the legal demand: the party
    making it, the applicable legislation or regulation, and what
    classes of person and resource it applies to.
    """

    status_code = status.unavailable_for_legal_reasons


class InternalServerError(HTTPError):
    """500 Internal Server Error.

    The server encountered an unexpected condition that prevented it
    from fulfilling the request.
    """

    status_code = status.internal_server_error


ServerError = InternalServerError
Error = InternalServerError


class NotImplemented(HTTPError):
    """501 Not Implemented.

    The 501 (Not Implemented) status code indicates that the server does
    not support the functionality required to fulfill the request.  This
    is the appropriate response when the server does not recognize the
    request method and is not capable of supporting it for any resource.
    """

    status_code = status.not_implemented


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

    status_code = status.insufficient_storage


class NetworkAuthenticationRequired(HTTPError):
    """511 Network Authentication Required.

    The 511 status code indicates that the client needs to authenticate
    to gain network access.
    """

    status_code = status.network_authentication_required
