import ast

import pytest

from proper.generators.channel import gen_channel


APP_NAME = "myapp"


@pytest.fixture()
def app_in_tmp(tmp_path, app):
    """A temporary app root with the channels/ directory pre-created."""
    app_root = tmp_path / APP_NAME
    channels_dir = app_root / "channels"
    channels_dir.mkdir(parents=True)
    (channels_dir / "__init__.py").write_text("")

    app.root_path = app_root
    app.name = APP_NAME
    return app


def test_generates_the_channel_class(app_in_tmp):
    gen_channel(app_in_tmp, "ChatRoom")

    text = (app_in_tmp.root_path / "channels" / "chat_room_channel.py").read_text()
    ast.parse(text)
    assert "class ChatRoomChannel(AppChannel):" in text
    assert "[[" not in text


def test_imports_the_channel_in_init(app_in_tmp):
    gen_channel(app_in_tmp, "ChatRoom")

    text = (app_in_tmp.root_path / "channels" / "__init__.py").read_text()
    assert "from . import chat_room_channel  # noqa" in text
