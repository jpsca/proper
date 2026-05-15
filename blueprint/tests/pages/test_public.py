def test_public_index(client):
    response = client.get("/")
    assert response.status == 200
    assert "Hello world!" in response.body
