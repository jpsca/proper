from [[app_name]].models import User, Session


@pytest.fixture()
def sign_in_as(client):
    def _sign_in_as(user):
        """Signs in as the given user using the provided test client."""
        session = Session.create_for_user(user=user)
        client.sign_in(session)
    return _sign_in_as


@pytest.fixture()
def signed_client(client, sign_in_as):
    """A test client with a signed-in user."""
    user = User.create(login="testuser", password="password123")
    sign_in_as(user)
    return client
