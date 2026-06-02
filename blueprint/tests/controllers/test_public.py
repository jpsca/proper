
def test_health_page(client):
    response = client.get("/health")
    assert response.status == 200


def test_not_found_page(client):
    response = client.get("/_not-found")
    # test page is rendered, not a 404
    assert response.status == 200


def test_error_page(client):
    response = client.get("/_error")
    # test page is rendered, not a 500
    assert response.status == 200
