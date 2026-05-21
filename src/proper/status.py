"""
HTTP status messages (plus some)
"""

# =========== Informational ===========

# Continue
http_continue = 100  # not just 'continue' because is a reserved word

# Switching Protocols
switching_protocols = 101

# Processing
processing = 102

# OK
ok = 200

# Created
created = 201

# Accepted
accepted = 202

# Non-Authoritative Information
non_authoritative_information = 203

# No Content
no_content = 204

# Reset Content
reset_content = 205

# Partial Content
partial_content = 206

# Multi-Status
multi_status = 207

# Already Reported
already_reported = 208

# IM Used
im_used = 226

# =========== Redirection ===========

# Multiple Choices
multiple_choices = 300

# Moved Permanently
moved_permanently = 301

# Found
found = 302

# See Other
see_other = 303

# Not Modified
not_modified = 304

# Use Proxy
use_proxy = 305

# Temporary Redirect
temporary_redirect = 307

# Permanent Redirect
permanent_redirect = 308

# =========== Client Error ===========

# Bad Request
bad_request = 400

# Unauthorized - means "not authenticated"
unauthorized = 401

# Payment Required
payment_required = 402

# Forbidden - means "not authorized"
forbidden = 403

# Not Found
not_found = 404

# Method Not Allowed
method_not_allowed = 405

# Not Acceptable
not_acceptable = 406

# Proxy Authentication Required
proxy_authentication_required = 407

# Request Time-out
request_timeout = 408

# Conflict
conflict = 409

# Gone
gone = 410

# Length Required
length_required = 411

# Precondition Failed
precondition_failed = 412

# Payload Too Large
request_entity_too_large = 413

# URI Too Long
request_uri_too_long = 414

# Unsupported Media Type
unsupported_media_type = 415

# Range Not Satisfiable
range_not_satisfiable = 416

# Expectation Failed
expectation_failed = 417

# Server refuses to brew coffee because it is a teapot
# I'm a teapot
im_a_teapot = 418

# Unprocessable Entity
unprocessable = 422
unprocessable_entity = 422

# Locked
locked = 423

# Failed Dependency
failed_dependency = 424

# Upgrade Required
upgrade_required = 426

# Precondition Required
precondition_required = 428

# Too Many Requests
too_many_requests = 429

# Request Header Fields Too Large
request_header_fields_too_large = 431

# Unavailable For Legal Reasons
unavailable_for_legal_reasons = 451

# =========== Server Error ===========

# Internal Server Error
internal_server_error = 500
server_error = 500

# Not Implemented
not_implemented = 501

# Bad Gateway
bad_gateway = 502

# Service Unavailable
service_unavailable = 503

# Gateway Timeout
gateway_timeout = 504

# HTTP Version Not Supported
http_version_not_supported = 505

# Insufficient Storage
insufficient_storage = 507

# Loop Detected
loop_detected = 508

# Network Authentication Required
network_authentication_required = 511

# =========== Special Cases ===========

# Meh
meh = 701

# Inconceivable
inconceivable = 720

# Works On My Machine
works_on_my_machine = 725

# A Feature Not A Bug
a_feature_not_a_bug = 726

# Computer Says No
computer_says_no = 740

# Under Caffeinated
under_caffeinated = 763
