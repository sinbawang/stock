"""
Chanlun (缠论) stock analysis framework.

Core modules for Chan theory structure identification:
- models: Data structures
- normalize: Bar inclusion handling
- fractal: Fractal (分型) detection
- bi: Stroke (笔) identification
- zhongshu: Center (中枢) detection
"""

__version__ = "0.1.0"

from .models import (
    Bar,
    NormalizedBar,
    Fractal,
    Bi,
    Segment,
    Zhongshu,
    FractalType,
    BiDirection,
)
from .segment import identify_segments
from .wechat import (
    WeChatConfig,
    WeChatMessenger,
    WeChatDependencyError,
    WeChatFriendNotFoundError,
)

__all__ = [
    "Bar",
    "NormalizedBar",
    "Fractal",
    "Bi",
    "Segment",
    "Zhongshu",
    "FractalType",
    "BiDirection",
    "identify_segments",
    "WeChatConfig",
    "WeChatMessenger",
    "WeChatDependencyError",
    "WeChatFriendNotFoundError",
]
