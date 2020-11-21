"""
HTTP status messages (plus some)

You can use the snake_case like `status.ok` or the
http_<code> version, like `status.http_400`.

"""


# Informational.
http_100 = "100 Continue"
http_continue = http_100  # not just 'continue' because is a reserved word

http_101 = "101 Switching Protocols"
switching_protocols = http_101

http_102 = "102 Processing"
processing = http_102


http_200 = "200 OK"
ok = http_200

http_201 = "201 Created"
created = http_201

http_202 = "202 Accepted"
accepted = http_202

http_203 = "203 Non-Authoritative Information"
non_authoritative_information = http_203

http_204 = "204 No Content"
no_content = http_204

http_205 = "205 Reset Content"
reset_content = http_205

http_206 = "206 Partial Content"
partial_content = http_206

http_207 = "207 Multi-Status"
multi_status = http_207

http_208 = "208 Already Reported"
already_reported = http_208

http_226 = "226 IM Used"
im_used = http_226


# Redirection
http_300 = "300 Multiple Choices"
multiple_choices = http_300

http_301 = "301 Moved Permanently"
moved_permanently = http_301

http_302 = "302 Found"
found = http_302

http_303 = "303 See Other"
see_other = http_303

http_304 = "304 Not Modified"
not_modified = http_304

http_305 = "305 Use Proxy"
use_proxy = http_305

http_307 = "307 Temporary Redirect"
temporary_redirect = http_307

http_308 = "308 Permanent Redirect"
permanent_redirect = http_308


# Client Error.
http_400 = "400 Bad Request"
bad_request = http_400

http_401 = "401 Unauthorized"  # means 'not authenticated'
unauthorized = http_401

http_402 = "402 Payment Required"
payment_required = http_402

http_403 = "403 Forbidden"  # means 'not authorized'
forbidden = http_403

http_404 = "404 Not Found"
not_found = http_404

http_405 = "405 Method Not Allowed"
method_not_allowed = http_405

http_406 = "406 Not Acceptable"
not_acceptable = http_406

http_407 = "407 Proxy Authentication Required"
proxy_authentication_required = http_407

http_408 = "408 Request Time-out"
request_timeout = http_408

http_409 = "409 Conflict"
conflict = http_409

http_410 = "410 Gone"
gone = http_410

http_411 = "411 Length Required"
length_required = http_411

http_412 = "412 Precondition Failed"
precondition_failed = http_412

http_413 = "413 Payload Too Large"
request_entity_too_large = http_413

http_414 = "414 URI Too Long"
request_uri_too_long = http_414

http_415 = "415 Unsupported Media Type"
unsupported_media_type = http_415

http_416 = "416 Range Not Satisfiable"
requested_range_not_satisfiable = http_416

http_417 = "417 Expectation Failed"
expectation_failed = http_417

# Server refuses to brew coffee because it is a teapot
http_418 = "418 I'm a teapot"
im_a_teapot = http_418

http_422 = "422 Unprocessable Entity"
unprocessable_entity = http_422

http_423 = "423 Locked"
locked = http_423

http_424 = "424 Failed Dependency"
failed_dependency = http_424

http_426 = "426 Upgrade Required"
upgrade_required = http_426

http_428 = "428 Precondition Required"
precondition_required = http_428

http_429 = "429 Too Many Requests"
too_many_requests = http_429

http_431 = "431 Request Header Fields Too Large"
request_header_fields_too_large = http_431

http_451 = "451 Unavailable For Legal Reasons"
unavailable_for_legal_reasons = http_451


# Server Error.
http_500 = "500 Internal Server Error"
internal_server_error = http_500
server_error = http_500

http_501 = "501 Not Implemented"
not_implemented = http_501

http_502 = "502 Bad Gateway"
bad_gateway = http_502

http_503 = "503 Service Unavailable"
service_unavailable = http_503

http_504 = "504 Gateway Timeout"
gateway_timeout = http_504

http_505 = "505 HTTP Version Not Supported"
http_version_not_supported = http_505

http_507 = "507 Insufficient Storage"
insufficient_storage = http_507

http_508 = "508 Loop Detected"
loop_detected = http_508

http_511 = "511 Network Authentication Required"
network_authentication_required = http_511


# Special Cases
http_701 = "701 Meh"
meh = http_701

http_720 = "720 Inconceivable"
inconceivable = http_720

http_725 = "725 Works On My Machine"
works_on_my_machine = http_725

http_726 = "726 A Feature Not A Bug"
a_feature_not_a_bug = http_726

http_740 = "740 Computer Says No"
computer_says_no = http_740

http_763 = "763 Under Caffeinated"
under_caffeinated = http_763
