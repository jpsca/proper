import typing as t
from io import BytesIO

import itsdangerous

from proper import current
from proper.constants import FLASHES_SESSION_KEY, GET, HEAD
from proper.errors import BadSignature
from proper.helpers import DotDict, MultiDict, Undefined, split_locale
from proper.router import Route

from .headers import RequestHeadersMixin
from .make_env import make_test_env
from .parse_form import parse_form, parse_query_string


__all__ = ("Request", )


class Request(RequestHeadersMixin):
    """An HTTP request.

    Arguments:

        encoding:
            Default encoding.

        max_content_length:
            Maximum content length in bytes.

        max_query_size:
            Maximum query string size in bytes.

        **env:
            A WSGI environment dict passed in from the server (See also PEP-3333).

    Attributes:

        env:
            The WSGI environment dict passed in from the server,
        with keys normalized to lower-case

        locale:
            Set in the `SetLocale` concern

        language:
            Just the language part of the locale. So `en_US` -> `en`.

        body:
            The request body as a bytes stream.

        accept:
            Indicates which content types, expressed as MIME types,
        the client is able to understand.

        accept_encoding:
            Indicates the content encoding (usually a compression algorithm) that
        the client can understand.

        accept_language:
            Indicates the natural language and locale that the client prefers.

        content_length:
            The length in bytes, as an integer, of the content
            sent by the client.

        content_type:
            The MIME content type of the incoming request.

        cookies:
            A dict with the cookies sent with the request.

        date:
            The date and time at which the message originated.

        default_port:
            Returns the default port (80 for HTTP, 443 for HTTPS)

        encoding:
            From the arguments.

        flashes:
            The flashed messages stored in the session cookie.
            By reading this value it will be stored in the request but
            deleted form the session.

        form:
            A `MultiDict` object containing the parsed body data, like the
            one sent by a HTML form with a POST, **including** the files.

        format:
            Computed based on the value of the "Accept" header, with "html"
        as a fallback.

        forwarded:
            A comma-separated list of forwarding information from the client
            to the server on its way through proxies.

        host, protocol, port, path, and query_string:
            Components of the URL used for the request, based on the pattern:
            `protocol://host:port/path?query_string`.

        host_with_port:
            A host:port string for this request. The port is not included
            if its the default for the protocol.

        if_none_match:
            A list of ETags provided by the client.

        if_modified_since:
            The date and time at which the client last modified the resource.

        is_get, is_head, is_post, is_put, is_patch, and is_delete:
            Return True or False based on the request method.

        is_ssl:
            Whether the current request was made via a SSL connection.

        is_xhr:
            True if current request is an XHR request.

        max_content_length:
            From the arguments.

        max_query_size:
            From the arguments.

        request_method:
            The uppercased request method, like: "GET".

        method:
            Returns the same value as `request_method` except for HEAD,
            which it returns as GET; or for POST if it has been overrided
            by PATCH, PUT, or DELETE (see `Method override`).

        port_is_default:
            Returns True or False, depending if the port is the default for
            the protocol.

        port_string:
            A `:port` string for the request if the port is not the default for
            the protocol.

        query:
            A `MultiDict` object containing the query string data.

        remote_ip:
            IP address of the closest client or proxy to the WSGI server.
            If your application is behind one or more reverse proxies,
            and it doesn't pass forward the IP address of the client,
            you can use the `access_route` attribute to retrieve the real
            IP address of the client.

        request_id:
            Parse the `x-request-id` header for a value that uniquely
            identify a request.

        session:
            The session data sent with the request.

        url:
            Returns the full URL used for the request.

        matched_route, matched_params, and matched_action:
            Added when the request match a route.

        csrf_token:
            A CSRF (Cross-Site Request Forgery) token.

        user:
            Added when the request comes from a logged-in user.

    """

    method: str
    path: str

    matched_route: Route | None = None
    matched_params: dict | None = None
    matched_action: str | None = None
    csrf_token: str = ""
    user: t.Any = None
    session: DotDict
    locale: str | None = None

    # Cache attrs
    _form: MultiDict | None = None
    _query: MultiDict | None = None

    def __init__(
        self,
        *,
        encoding: str = "utf8",
        max_content_length: int = -1,
        max_query_size: int | None = None,
        **env,
    ) -> None:
        self.encoding = encoding
        self.max_content_length = max_content_length
        self.max_query_size = max_query_size
        self.session = DotDict()

        env = env or make_test_env()
        super().__init__(env)

    def __repr__(self) -> str:
        return f"<Request {self.method} “{self.path}”>"

    @property
    def language(self) -> str | None:
        if self.locale:
            return split_locale(self.locale)[0]

    @property
    def body(self) -> BytesIO:
        """The request body as a BytesIO stream."""
        return self.env.get("wsgi.input") or BytesIO()

    @property
    def flashes(self) -> dict:
        """The flashed messages stored in the session cookie."""
        return self.session.get(FLASHES_SESSION_KEY, {})

    @property
    def form(self) -> MultiDict:
        """A `MultiDict` object containing the parsed body data, like the
        one sent by a HTML form with a POST, **including** the files.
        """
        if self._form is None:
            self._form = self._parse_form()
        return self._form

    def _parse_form(self) -> MultiDict:
        # GET and HEAD can't have form data.
        if self.method in (GET, HEAD):
            return MultiDict()

        return parse_form(
            self.body,
            self.content_type,
            self.content_length,
            encoding=self.encoding,
            max_content_length=self.max_content_length,
        )

    @property
    def query(self) -> MultiDict:
        """A `MultiDict` object containing the query string data."""
        if self._query is None:
            self._query = self._parse_query()
        return self._query

    def _parse_query(self) -> MultiDict:
        return parse_query_string(
            self.query_string,
            encoding=self.encoding,
            max_query_size=self.max_query_size,
        )

    @property
    def query_string(self) -> str:
        """Returns the query string."""
        return self.env.get("query_string", "")

    @property
    def url(self) -> str:
        """Returns the current URL."""
        return self.get_url()

    def get_url(self, include_query: bool = True) -> str:
        """Returns the current URL, optionally including the query string"""
        url = self.path
        if include_query and self.query_string:
            url = f"{url}?{self.query_string}"
        return url

    def get_signed_cookie(
            self,
            name: str,
            default: t.Any = Undefined,
            *,
            salt: str = "",
            max_age: int | None = None,
        ) -> str | t.Any:
        """
        Returns a cookie value for a signed cookie, or raises a `ValueError` if
        there is no cookie with that name, or a `proper.errors.BadSignature`
        exception if the signature is no longer valid.

        If you provide the `default` argument the exceptions will be suppressed and
        that default value will be returned instead.

        The optional salt argument can be used to provide extra protection against
        brute force attacks on your secret key. If supplied, the `max_age` argument
        will be checked against the signed timestamp attached to the cookie value
        to ensure the cookie is not older than `max_age` seconds.

        For example:

        $ request.get_signed_cookie("name")
        'Jon'
        $ request.get_signed_cookie("name", salt="name-salt")
        'Jon' # assuming cookie was set using the same salt
        $ request.get_signed_cookie("nonexistent-cookie")
        KeyError: 'nonexistent-cookie'
        $ request.get_signed_cookie("nonexistent-cookie", False)
        False
        $ request.get_signed_cookie("cookie-that-was-tampered-with")
        BadSignature: ...
        $ request.get_signed_cookie("name", max_age=60)
        SignatureExpired: Signature age 1677.3839159 > 60 seconds
        $ request.get_signed_cookie("name", False, max_age=60)
        False
"""
        signer = current.app.get_signer(salt)
        signed_value = self.cookies.get(name)
        if not signed_value:
            if default is not Undefined:
                return default
            else:
                raise ValueError("Cookie not set")

        try:
            value = signer.unsign(signed_value, max_age=max_age)
            if isinstance(value, bytes):
                return value.decode()
            else:
                return value

        except itsdangerous.BadSignature as err:
            if default is not Undefined:
                return default
            raise BadSignature() from err
