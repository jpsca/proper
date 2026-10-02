import json

import pytest

from proper import TestClient
from proper.controller import Controller
from proper.router import Route


class UploadsController(Controller):
    def create(self):
        upload = self.params["photo"]
        data = {
            "filename": upload.filename,
            "content_type": upload.content_type,
            "content": upload.file.read().decode(),
            "title": self.params.get("title"),
        }
        self.response.body = json.dumps(data)


@pytest.fixture()
def client(app):
    app.router.add_route(Route(method="POST", path="uploads", to=UploadsController.create))
    return TestClient(app)


def test_upload_sends_the_name_of_the_file(client, tmp_path):
    """Regression: the path given to the client was sent as the name of
    the file. A browser only sends the name."""
    folder = tmp_path / "fixtures"
    folder.mkdir()
    path = folder / "sunset.txt"
    path.write_text("hello")

    response = client.post("/uploads", body={"title": "Sunset"}, upload_files=[("photo", path)])

    assert json.loads(response.body) == {
        "filename": "sunset.txt",
        "content_type": "text/plain",
        "content": "hello",
        "title": "Sunset",
    }


def test_upload_from_a_path_as_string(client, tmp_path):
    path = tmp_path / "data.bin"
    path.write_text("x")

    response = client.post("/uploads", upload_files=[("photo", str(path))])

    data = json.loads(response.body)
    assert data["filename"] == "data.bin"
    assert data["content_type"] == "application/octet-stream"


def test_upload_of_a_file_with_quotes_in_its_name(client, tmp_path):
    path = tmp_path / 'my "best" photo.txt'
    path.write_text("x")

    response = client.post("/uploads", upload_files=[("photo", path)])

    assert json.loads(response.body)["filename"] == "my %22best%22 photo.txt"
