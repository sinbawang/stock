"""
微信消息模块单元测试。
"""

from pathlib import Path

import pytest

from chanlun.wechat import WeChatMessenger, WeChatFriendNotFoundError


class _FakeItchat:
    def __init__(self):
        self.auto_login_called = False
        self.logout_called = False
        self.send_msg_calls = []
        self.send_image_calls = []
        self.friend_map = {
            "张三": [{"NickName": "张三", "RemarkName": "老张", "UserName": "@friend_zhang"}],
            "老张": [{"NickName": "张三", "RemarkName": "老张", "UserName": "@friend_zhang"}],
        }

    def auto_login(self, hotReload, statusStorageDir, enableCmdQR):  # noqa: N803
        self.auto_login_called = True
        return {
            "hotReload": hotReload,
            "statusStorageDir": statusStorageDir,
            "enableCmdQR": enableCmdQR,
        }

    def logout(self):
        self.logout_called = True

    def search_friends(self, name=None):
        return self.friend_map.get(name, [])

    def send_msg(self, msg, toUserName):  # noqa: N803
        self.send_msg_calls.append((msg, toUserName))
        return {"BaseResponse": {"Ret": 0}}

    def send_image(self, image_path, toUserName):  # noqa: N803
        self.send_image_calls.append((image_path, toUserName))
        return {"BaseResponse": {"Ret": 0}}


@pytest.fixture
def messenger(monkeypatch):
    fake = _FakeItchat()
    monkeypatch.setattr(WeChatMessenger, "_load_itchat_module", staticmethod(lambda: fake))
    return WeChatMessenger(), fake


def test_send_text_to_friend(messenger):
    m, fake = messenger
    result = m.send_text("张三", "你好")

    assert fake.auto_login_called is True
    assert fake.send_msg_calls == [("你好", "@friend_zhang")]
    assert result["BaseResponse"]["Ret"] == 0


def test_send_image_to_friend(messenger, tmp_path: Path):
    m, fake = messenger
    image = tmp_path / "demo.png"
    image.write_bytes(b"fake")

    result = m.send_image("老张", str(image))

    assert fake.auto_login_called is True
    assert len(fake.send_image_calls) == 1
    sent_image, sent_to = fake.send_image_calls[0]
    assert sent_to == "@friend_zhang"
    assert sent_image.endswith("demo.png")
    assert result["BaseResponse"]["Ret"] == 0


def test_friend_not_found(messenger):
    m, _ = messenger
    with pytest.raises(WeChatFriendNotFoundError):
        m.send_text("不存在的好友", "hello")
