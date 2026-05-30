from formidable import MESSAGES
from formidable.errors import (
  AFTER_DATE,
  AFTER_TIME,
  BEFORE_DATE,
  BEFORE_TIME,
  FUTURE_DATE,
  FUTURE_TIME,
  GT,
  GTE,
  INVALID,
  INVALID_EMAIL,
  INVALID_JSON,
  INVALID_SLUG,
  INVALID_URL,
  LT,
  LTE,
  MAX_ITEMS,
  MAX_LENGTH,
  MIN_ITEMS,
  MIN_LENGTH,
  MULTIPLE_OF,
  ONE_OF,
  PAST_DATE,
  PAST_TIME,
  PATTERN,
  REQUIRED,
)


FILE_TOO_LARGE = "file_too_large"
INVALID_CONTENT_TYPE = "invalid_content_type"

MESSAGES[FILE_TOO_LARGE] = "File size should be {max_size} or less"
MESSAGES[INVALID_CONTENT_TYPE] = "Invalid content type"


__all__ = (
    "AFTER_DATE",
    "AFTER_TIME",
    "BEFORE_DATE",
    "BEFORE_TIME",
    "FUTURE_DATE",
    "FUTURE_TIME",
    "GT",
    "GTE",
    "INVALID",
    "INVALID_EMAIL",
    "INVALID_JSON",
    "INVALID_SLUG",
    "INVALID_URL",
    "LT",
    "LTE",
    "MAX_ITEMS",
    "MAX_LENGTH",
    "MIN_ITEMS",
    "MIN_LENGTH",
    "MULTIPLE_OF",
    "ONE_OF",
    "PAST_DATE",
    "PAST_TIME",
    "PATTERN",
    "REQUIRED",
    "FILE_TOO_LARGE",
    "INVALID_CONTENT_TYPE",
    "MESSAGES",
)
