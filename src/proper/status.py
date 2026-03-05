"""
HTTP status messages (plus some)

You can use the snake_case like `status.ok` or the
http_CODE version, like `status.http_400`.
"""
from typing import Final


# Informational.
http_100: Final = "100 Continue"
http_continue = 100  # not just 'continue' because is a reserved word

http_101: Final = "101 Switching Protocols"
switching_protocols = 101

http_102: Final = "102 Processing"
processing = 102

http_200: Final = "200 OK"
ok = 200

http_201: Final = "201 Created"
created = 201

http_202: Final = "202 Accepted"
accepted = 202

http_203: Final = "203 Non-Authoritative Information"
non_authoritative_information = 203

http_204: Final = "204 No Content"
no_content = 204

http_205: Final = "205 Reset Content"
reset_content = 205

http_206: Final = "206 Partial Content"
partial_content = 206

http_207: Final = "207 Multi-Status"
multi_status = 207

http_208: Final = "208 Already Reported"
already_reported = 208

http_226: Final = "226 IM Used"
im_used = 226


# Redirection
http_300: Final = "300 Multiple Choices"
multiple_choices = 300

http_301: Final = "301 Moved Permanently"
moved_permanently = 301

http_302: Final = "302 Found"
found = 302

http_303: Final = "303 See Other"
see_other = 303

http_304: Final = "304 Not Modified"
not_modified = 304

http_305: Final = "305 Use Proxy"
use_proxy = 305

http_307: Final = "307 Temporary Redirect"
temporary_redirect = 307

http_308: Final = "308 Permanent Redirect"
permanent_redirect = 308


# Client Error.
http_400: Final = "400 Bad Request"
bad_request = 400

http_401: Final = "401 Unauthorized"  # means 'not authenticated'
unauthorized = 401

http_402: Final = "402 Payment Required"
payment_required = 402

http_403: Final = "403 Forbidden"  # means 'not authorized'
forbidden = 403

http_404: Final = "404 Not Found"
not_found = 404

http_405: Final = "405 Method Not Allowed"
method_not_allowed = 405

http_406: Final = "406 Not Acceptable"
not_acceptable = 406

http_407: Final = "407 Proxy Authentication Required"
proxy_authentication_required = 407

http_408: Final = "408 Request Time-out"
request_timeout = 408

http_409: Final = "409 Conflict"
conflict = 409

http_410: Final = "410 Gone"
gone = 410

http_411: Final = "411 Length Required"
length_required = 411

http_412: Final = "412 Precondition Failed"
precondition_failed = 412

http_413: Final = "413 Payload Too Large"
request_entity_too_large = 413

http_414: Final = "414 URI Too Long"
request_uri_too_long = 414

http_415: Final = "415 Unsupported Media Type"
unsupported_media_type = 415

http_416: Final = "416 Range Not Satisfiable"
range_not_satisfiable = 416

http_417: Final = "417 Expectation Failed"
expectation_failed = 417

# Server refuses to brew coffee because it is a teapot
http_418: Final = "418 I'm a teapot"
im_a_teapot = 418

http_422: Final = "422 Unprocessable Entity"
unprocessable = 422
unprocessable_entity = 422

http_423: Final = "423 Locked"
locked = 423

http_424: Final = "424 Failed Dependency"
failed_dependency = 424

http_426: Final = "426 Upgrade Required"
upgrade_required = 426

http_428: Final = "428 Precondition Required"
precondition_required = 428

http_429: Final = "429 Too Many Requests"
too_many_requests = 429

http_431: Final = "431 Request Header Fields Too Large"
request_header_fields_too_large = 431

http_451: Final = "451 Unavailable For Legal Reasons"
unavailable_for_legal_reasons = 451


# Server Error.
http_500: Final = "500 Internal Server Error"
internal_server_error = 500
server_error = 500

http_501: Final = "501 Not Implemented"
not_implemented = 501

http_502: Final = "502 Bad Gateway"
bad_gateway = 502

http_503: Final = "503 Service Unavailable"
service_unavailable = 503

http_504: Final = "504 Gateway Timeout"
gateway_timeout = 504

http_505: Final = "505 HTTP Version Not Supported"
http_version_not_supported = 505

http_507: Final = "507 Insufficient Storage"
insufficient_storage = 507

http_508: Final = "508 Loop Detected"
loop_detected = 508

http_511: Final = "511 Network Authentication Required"
network_authentication_required = 511


# Special Cases
http_701: Final = "701 Meh"
meh = 701

http_720: Final = "720 Inconceivable"
inconceivable = 720

http_725: Final = "725 Works On My Machine"
works_on_my_machine = 725

http_726: Final = "726 A Feature Not A Bug"
a_feature_not_a_bug = 726

http_740: Final = "740 Computer Says No"
computer_says_no = 740

http_763: Final = "763 Under Caffeinated"
under_caffeinated = 763
