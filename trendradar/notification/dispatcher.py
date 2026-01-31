# coding=utf-8 ＇
"""
通知分发调度器（Dispatcher）

兼容旧版 / 新版 TrendRadar 的调用方式
"""

class NotificationDispatcher:
    def __init__(self, *args, **kwargs):
        """
        兼容：
        - NotificationDispatcher()
        - NotificationDispatcher(config=xxx)
        """
        self.config = kwargs.get("config", {}) or {}

    def dispatch(self, *args, **kwargs):
        """
        单次分发（兜底实现）
        实际推送逻辑已在 notification.send_to_xxx 中完成
        """
        return

    def dispatch_all(self, *args, **kwargs):
        """
        兼容旧版本调用：
        dispatcher.dispatch_all(...)
        """
        return self.dispatch(*args, **kwargs)