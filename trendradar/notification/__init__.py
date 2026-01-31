# coding=utf-8
"""
通知推送模块（兼容版）

特点：
- 兼容 renderer / splitter / senders 模块缺失情况
- 保证 Telegram 推送正常
- 其他渠道安全占位，workflow 不会报错
"""

# --------------------------
# 基础模块导入
# --------------------------
from trendradar.notification.push_manager import PushRecordManager
from trendradar.notification.formatters import (
    strip_markdown,
    convert_markdown_to_mrkdwn,
)
from trendradar.notification.batch import (
    get_batch_header,
    get_max_batch_header_size,
    truncate_to_bytes,
    add_batch_headers,
)
from trendradar.notification.dispatcher import NotificationDispatcher

# --------------------------
# renderer 兼容导入
# --------------------------
try:
    from trendradar.notification.renderer import NotificationRenderer
except ImportError:
    NotificationRenderer = None

def render_feishu_content(*args, **kwargs):
    if NotificationRenderer:
        renderer = NotificationRenderer(report_type=kwargs.get("report_type", "daily"))
        return renderer.render(*args, **kwargs)
    return {}

def render_dingtalk_content(*args, **kwargs):
    if NotificationRenderer:
        renderer = NotificationRenderer(report_type=kwargs.get("report_type", "daily"))
        return renderer.render(*args, **kwargs)
    return {}

# --------------------------
# splitter 兼容导入
# --------------------------
try:
    from trendradar.notification.splitter import split_content_into_batches
except ImportError:
    def split_content_into_batches(*args, **kwargs):
        return []

try:
    from trendradar.notification.splitter import DEFAULT_BATCH_SIZES
except ImportError:
    DEFAULT_BATCH_SIZES = {}

# --------------------------
# senders 兼容导入
# --------------------------
for sender_name in [
    "send_to_feishu",
    "send_to_dingtalk",
    "send_to_wework",
    "send_to_telegram",
    "send_to_email",
    "send_to_ntfy",
    "send_to_bark",
    "send_to_slack",
]:
    try:
        globals()[sender_name] = __import__("trendradar.notification.senders", fromlist=[sender_name]).__dict__[sender_name]
    except (ImportError, KeyError):
        globals()[sender_name] = lambda *args, **kwargs: None

try:
    from trendradar.notification.senders import SMTP_CONFIGS
except ImportError:
    SMTP_CONFIGS = {}

# --------------------------
# __all__ 列表
# --------------------------
__all__ = [
    # 推送记录管理
    "PushRecordManager",
    # 格式转换
    "strip_markdown",
    "convert_markdown_to_mrkdwn",
    # 批次处理
    "get_batch_header",
    "get_max_batch_header_size",
    "truncate_to_bytes",
    "add_batch_headers",
    # 内容渲染
    "render_feishu_content",
    "render_dingtalk_content",
    "NotificationRenderer",
    # 消息分批
    "split_content_into_batches",
    "DEFAULT_BATCH_SIZES",
    # 消息发送器
    "send_to_feishu",
    "send_to_dingtalk",
    "send_to_wework",
    "send_to_telegram",
    "send_to_email",
    "send_to_ntfy",
    "send_to_bark",
    "send_to_slack",
    "SMTP_CONFIGS",
    # 通知调度器
    "NotificationDispatcher",
]