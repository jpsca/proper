from proper.channels import Channel


try:
    from ..models import Session
except ImportError:
    # The auth addon is not installed, so channels stay anonymous.
    Session = None


class AppChannel(Channel):
    """All channels should inherit from this class.

    When the auth addon is installed, `Session` is wired to your app's session
    model, so the connection is authenticated from the signed login cookie:
    `current.user` and `self.authenticated` are then available in every channel
    method. Without the auth addon, channels stay anonymous.
    """

    Session = Session
