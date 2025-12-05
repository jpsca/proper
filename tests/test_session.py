# from http.cookies import Morsel

# import pytest

# from proper import Request, Response
# from proper.concerns import (
#     SESSION_COOKIE,
#     SESSION_SALT,
#     RestoreSession,
#     UpdateSessionCookie,
# )
# from proper.controller import Controller


# @pytest.fixture
# def co(app):
#     request = Request()
#     response = Response()
#     return Controller(app, request, response)


# def _set_request_cookie(app, co, value):
#     cookie = Morsel()
#     cookie.set(SESSION_COOKIE, value, 0)
#     co.request.cookie = {SESSION_COOKIE: cookie}


# @pytest.mark.skip(reason="Needs investigation")
# def test_fetch_session(app, co):
#     concern = RestoreSession()
#     data = {"hello": "world!"}
#     _set_request_cookie(app, co, app.serializer.dumps(data, salt=SESSION_SALT))
#     concern(co)

#     assert co.request.session == co.response.session == data


# # def test_do_not_copy_flashes(app, co):
# #     concern = RestoreSession()
# #     data = {"hello": "world!"}
# #     ext_data = {FLASHES_SESSION_KEY: "...", **data}
# #     _set_request_cookie(app, co, app.serializer.dumps(ext_data, salt=SESSION_SALT))
# #     concern(co)

# #     assert co.request.session == ext_data
# #     assert co.response.session == data


# @pytest.mark.skip(reason="Needs investigation")
# def test_fetch_session_bad_cookie(app, co):
#     concern = RestoreSession()
#     _set_request_cookie(app, co, "bad cookie")
#     concern(co)

#     assert co.request.session == co.response.session == {}


# @pytest.mark.skip(reason="Needs investigation")
# def test_do_not_set_cookie_if_not_data(app, co):
#     concern = UpdateSessionCookie()
#     co.request.session = {}
#     co.response.session = {}
#     concern(co)

#     assert SESSION_COOKIE not in co.response.cookies


# @pytest.mark.skip(reason="Needs investigation")
# def test_set_delete_cookie_if_not_data_and_modified(app, co):
#     concern = UpdateSessionCookie()
#     co.request.session = {"foo": "bar"}
#     co.response.session = {}
#     concern(co)

#     assert SESSION_COOKIE in co.response.cookies
#     assert co.response.cookies[SESSION_COOKIE]["max-age"] == 0
