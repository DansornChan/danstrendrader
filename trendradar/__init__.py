# coding=utf-8
"""
TrendRadar - 热点新闻聚合与分析工具

使用方式:
  python -m trendradar        # 模块执行
  trendradar                  # 安装后执行
"""

from trendradar.context import AppContext

__version__ = "5.3.0"
__all__ = ["AppContext", "__version__"]

# ---- 通知模块兼容导入 ----
try:
    from trendradar.notification.telegram import send_telegram_message
except ImportError:
    send_telegram_message = None

try:
    from trendradar.notification.email import send_email_message
except ImportError:
    send_email_message = None

try:
    # Feishu 函数可能已删除或改名，这里用安全方式导入
    from trendradar.notification.renderer import (
        render_generic_content,
        render_dingtalk_content,
        render_wework_content
    )
except ImportError:
    render_generic_content = None
    render_dingtalk_content = None
    render_wework_content = None

# 方便直接在模块里使用通知函数
__all__.extend([
    "send_telegram_message",
    "send_email_message",
    "render_generic_content",
    "render_dingtalk_content",
    "render_wework_content"
])