from proper.channels import Channel
from proper.models.base import ProperModel


try:
    from ..models import Session, User
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

    def find_user(self, user_id) -> "User | None":
        """Load the connection's user by id. Called before every dispatch
        after `subscribed()` to refresh `current.user` from the database.
        Adapt to your needs (for example, to filter out inactive users).
        """
        return User.get_or_none(User.id == user_id)
