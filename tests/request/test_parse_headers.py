from proper import Request, make_test_env


def parse_whatever():
    env = make_test_env(HTTP_WHATEVER="meh")
    req = Request(**env)
    assert req.get_header("whatever") == "meh"


def test_parse_accept_header():
    env = make_test_env(HTTP_ACCEPT="text/html, application/xml;q=0.9, */*;q=0.8")
    req = Request(**env)

    assert req.accept == [
        "text/html",
        "application/xml",
        "*/*",
    ]
