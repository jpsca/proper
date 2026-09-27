"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

import logging
import uuid


logger = logging.getLogger("jx")


def get_random_id(prefix: str = "id") -> str:
    """
    Returns an unique string suitable to be used for HTML element IDs.

    HTML form elements, popovers, and other components require unique IDs
    to function correctly. When you are writing custom components, this function
    can be used to generate default IDs for such elements, so you don't have to
    make it a required argument.

    Arguments:
        prefix: The prefix to use for the ID. Defaults to "id".

    """
    return f"{prefix}-{uuid.uuid4().hex}"

