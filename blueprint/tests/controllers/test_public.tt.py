from [[app_name]].main import app


def test_health_page(client):
    response = client.get(app.url_for("Public.health"))
    assert response.status == 200


def test_not_found_page(client):
    response = client.get(app.url_for("Public.not_found"))
    # test page is rendered, not a 404
    assert response.status == 200


def test_error_page(client):
    response = client.get(app.url_for("Public.error"))
    # test page is rendered, not a 500
    assert response.status == 200
