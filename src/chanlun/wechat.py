"""
个人微信好友消息发送模块。

基于 itchat 协议封装，支持：
- 发送文本消息给微信好友
- 发送图片消息给微信好友

使用前请先安装依赖：
    pip install itchat-uos
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
import importlib


class WeChatDependencyError(RuntimeError):
    """缺少微信发送依赖。"""


class WeChatFriendNotFoundError(RuntimeError):
    """未找到匹配的微信好友。"""


@dataclass
class WeChatConfig:
    """微信登录配置。"""

    hot_reload: bool = True
    status_storage_dir: str = "./.wechat"
    status_storage_file: str = "itchat.pkl"
    enable_cmd_qr: int = 2

    @property
    def status_storage_path(self) -> Path:
        return Path(self.status_storage_dir) / self.status_storage_file


class WeChatMessenger:
    """
    微信好友消息发送器。

    说明：
    1. 第一次登录需要扫码。
    2. 成功登录后会保存登录状态，后续可复用。
    """

    def __init__(self, config: Optional[WeChatConfig] = None):
        self.config = config or WeChatConfig()
        self._itchat = self._load_itchat_module()
        self._is_logged_in = False

    @staticmethod
    def _load_itchat_module() -> Any:
        try:
            return importlib.import_module("itchat")
        except Exception as exc:
            raise WeChatDependencyError(
                "未安装 itchat 依赖。请先执行: pip install itchat-uos"
            ) from exc

    def login(self) -> None:
        """登录微信。"""
        status_path = self.config.status_storage_path
        status_path.parent.mkdir(parents=True, exist_ok=True)

        self._itchat.auto_login(
            hotReload=self.config.hot_reload,
            statusStorageDir=str(status_path),
            enableCmdQR=self.config.enable_cmd_qr,
        )
        self._is_logged_in = True

    def logout(self) -> None:
        """退出微信登录。"""
        if self._is_logged_in:
            self._itchat.logout()
            self._is_logged_in = False

    def _ensure_login(self) -> None:
        if not self._is_logged_in:
            self.login()

    def resolve_friend_username(self, friend_keyword: str) -> str:
        """
        按昵称/备注查找好友并返回 UserName。

        参数：
            friend_keyword: 好友昵称或备注关键字；若以 '@' 开头则视为 UserName。
        """
        if friend_keyword.startswith("@"):
            return friend_keyword

        self._ensure_login()
        candidates = self._itchat.search_friends(name=friend_keyword) or []

        if not candidates:
            raise WeChatFriendNotFoundError(f"未找到好友: {friend_keyword}")

        for item in candidates:
            if item.get("NickName") == friend_keyword or item.get("RemarkName") == friend_keyword:
                return item["UserName"]

        return candidates[0]["UserName"]

    def send_text(self, friend_keyword: str, text: str) -> Any:
        """发送文本消息。"""
        if not text:
            raise ValueError("text 不能为空")

        to_user = self.resolve_friend_username(friend_keyword)
        self._ensure_login()
        return self._itchat.send_msg(msg=text, toUserName=to_user)

    def send_image(self, friend_keyword: str, image_path: str) -> Any:
        """发送图片消息。"""
        image = Path(image_path)
        if not image.exists() or not image.is_file():
            raise FileNotFoundError(f"图片不存在: {image_path}")

        to_user = self.resolve_friend_username(friend_keyword)
        self._ensure_login()
        return self._itchat.send_image(str(image.resolve()), toUserName=to_user)

    def send_text_and_image(self, friend_keyword: str, text: str, image_path: str) -> None:
        """先发送文本，再发送图片。"""
        self.send_text(friend_keyword, text)
        self.send_image(friend_keyword, image_path)
