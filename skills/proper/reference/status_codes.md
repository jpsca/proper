---
title: Status Codes
description: Reference: every constant of `proper.status` with its number
last_verified: 2026-11-07
sources:
  - src/proper/status.py
---

# Status Codes

Read this only to confirm the name of a status constant. The error classes to raise from a controller are in [rendering.md](../rendering.md#raising-http-errors).

## Status Codes

Import as `from proper import status` or `from proper.status import ok, not_found, ...`.

### Informational (1xx)

| Constant                | Value |
|-------------------------|-------|
| `http_continue`         | 100   |
| `switching_protocols`   | 101   |
| `processing`            | 102   |

### Successful (2xx)

| Constant                          | Value |
|-----------------------------------|-------|
| `ok`                              | 200   |
| `created`                         | 201   |
| `accepted`                        | 202   |
| `non_authoritative_information`   | 203   |
| `no_content`                      | 204   |
| `reset_content`                   | 205   |
| `partial_content`                 | 206   |
| `multi_status`                    | 207   |
| `already_reported`                | 208   |
| `im_used`                         | 226   |

### Redirection (3xx)

| Constant               | Value |
|------------------------|-------|
| `multiple_choices`     | 300   |
| `moved_permanently`    | 301   |
| `found`                | 302   |
| `see_other`            | 303   |
| `not_modified`         | 304   |
| `use_proxy`            | 305   |
| `temporary_redirect`   | 307   |
| `permanent_redirect`   | 308   |

### Client Error (4xx)

| Constant                           | Value |
|------------------------------------|-------|
| `bad_request`                      | 400   |
| `unauthorized`                     | 401   |
| `payment_required`                 | 402   |
| `forbidden`                        | 403   |
| `not_found`                        | 404   |
| `method_not_allowed`               | 405   |
| `not_acceptable`                   | 406   |
| `proxy_authentication_required`    | 407   |
| `request_timeout`                  | 408   |
| `conflict`                         | 409   |
| `gone`                             | 410   |
| `length_required`                  | 411   |
| `precondition_failed`              | 412   |
| `request_entity_too_large`         | 413   |
| `request_uri_too_long`             | 414   |
| `unsupported_media_type`           | 415   |
| `range_not_satisfiable`            | 416   |
| `expectation_failed`               | 417   |
| `im_a_teapot`                      | 418   |
| `unprocessable` / `unprocessable_entity` | 422 |
| `locked`                           | 423   |
| `failed_dependency`                | 424   |
| `upgrade_required`                 | 426   |
| `precondition_required`            | 428   |
| `too_many_requests`                | 429   |
| `request_header_fields_too_large`  | 431   |
| `unavailable_for_legal_reasons`    | 451   |

### Server Error (5xx)

| Constant                           | Value |
|------------------------------------|-------|
| `internal_server_error` / `server_error` | 500 |
| `not_implemented`                  | 501   |
| `bad_gateway`                      | 502   |
| `service_unavailable`              | 503   |
| `gateway_timeout`                  | 504   |
| `http_version_not_supported`       | 505   |
| `insufficient_storage`             | 507   |
| `loop_detected`                    | 508   |
| `network_authentication_required`  | 511   |

### Unofficial (7xx)

| Constant               | Value |
|------------------------|-------|
| `meh`                  | 701   |
| `inconceivable`        | 720   |
| `works_on_my_machine`  | 725   |
| `a_feature_not_a_bug`  | 726   |
| `computer_says_no`     | 740   |
| `under_caffeinated`    | 763   |
