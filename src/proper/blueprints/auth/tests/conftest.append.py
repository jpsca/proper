from [[app_name]].models import User, Session


@pytest.fixture()
def signed_client(client):
    """A test client with a signed-in user."""
    user = User.create(login="testuser", password="password123")
    session = Session.create_for_user(user=user)
    client.sign_in(session)
    return client
