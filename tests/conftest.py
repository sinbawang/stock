"""
共享 pytest fixtures。
"""

import socket
from datetime import datetime

import pytest
import requests

from chanlun.models import Bar, NormalizedBar

# --- 测试网络安全网（仅测试会话内生效） ---
# 本机对部分行情/资金流数据源（Eastmoney / AkShare 等）存在病理性连通问题：
# 连接可以建立，但服务端不返回数据，导致无显式 timeout 的 requests 调用无限阻塞，
# 进而把全量测试永久卡死（此前 03690 HK 数据源与资金流抓取均踩过这个坑）。
# 这里在测试会话层面注入默认超时：
#   1) socket.setdefaulttimeout 兜住裸 socket；
#   2) 包装 requests.Session.request，凡未显式传 timeout 的调用一律补上默认超时。
# 生产代码不受影响（显式传入 timeout 的调用原样透传）。
_TEST_NETWORK_TIMEOUT = 15

socket.setdefaulttimeout(_TEST_NETWORK_TIMEOUT)

_original_session_request = requests.Session.request


def _session_request_with_default_timeout(self, method, url, **kwargs):
    if kwargs.get("timeout") is None:
        kwargs["timeout"] = _TEST_NETWORK_TIMEOUT
    return _original_session_request(self, method, url, **kwargs)


requests.Session.request = _session_request_with_default_timeout


@pytest.fixture
def sample_bars():
    return [
        Bar(ts=datetime(2024, 1, 1), open=100, high=102, low=99, close=101, volume=1000),
        Bar(ts=datetime(2024, 1, 2), open=101, high=103, low=100, close=102, volume=1100),
        Bar(ts=datetime(2024, 1, 3), open=102, high=104, low=101, close=103, volume=1200),
        Bar(ts=datetime(2024, 1, 4), open=103, high=105, low=102, close=104, volume=1300),
        Bar(ts=datetime(2024, 1, 5), open=104, high=106, low=103, close=105, volume=1400),
    ]


@pytest.fixture
def sample_bars_with_inclusion():
    return [
        Bar(ts=datetime(2024, 1, 1), open=100, high=102, low=99, close=101, volume=1000),
        Bar(ts=datetime(2024, 1, 2), open=101, high=105, low=98, close=102, volume=1100),
        Bar(ts=datetime(2024, 1, 3), open=102, high=103, low=100, close=101, volume=1200),
        Bar(ts=datetime(2024, 1, 4), open=101, high=104, low=99, close=103, volume=1300),
    ]


@pytest.fixture
def sample_normalized_bars():
    return [
        NormalizedBar(
            idx=0,
            high=102,
            low=99,
            ts_start=datetime(2024, 1, 1),
            ts_end=datetime(2024, 1, 1),
            src_indices=[0],
        ),
        NormalizedBar(
            idx=1,
            high=103,
            low=100,
            ts_start=datetime(2024, 1, 2),
            ts_end=datetime(2024, 1, 2),
            src_indices=[1],
        ),
        NormalizedBar(
            idx=2,
            high=104,
            low=101,
            ts_start=datetime(2024, 1, 3),
            ts_end=datetime(2024, 1, 3),
            src_indices=[2],
        ),
        NormalizedBar(
            idx=3,
            high=105,
            low=102,
            ts_start=datetime(2024, 1, 4),
            ts_end=datetime(2024, 1, 4),
            src_indices=[3],
        ),
        NormalizedBar(
            idx=4,
            high=106,
            low=103,
            ts_start=datetime(2024, 1, 5),
            ts_end=datetime(2024, 1, 5),
            src_indices=[4],
        ),
    ]
