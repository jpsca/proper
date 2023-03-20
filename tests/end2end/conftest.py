import pytest


class FakeStartResponse:
    status_code = headers_list = None

    def __call__(self, status_code, headers_list):
        self.status_code = status_code
        self._headers = dict(headers_list)


@pytest.fixture(scope="session")
def start_response():
    return FakeStartResponse()
