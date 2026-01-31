# coding=utf-8
"""
极简 NotificationDispatcher
兼容 TrendRadar 内置 TelegramSender
"""

from trendradar.notification.senders import TelegramSender


class NotificationDispatcher:
    def __init__(self, *args, **kwargs):
        # TelegramSender 内部会自行读取环境变量
        self.sender = TelegramSender()

    def dispatch(self, content, *args, **kwargs):
        print("📨 Dispatcher: 开始发送 Telegram 消息")

        if content is None:
            print("⚠️ Dispatcher: 内容为空，跳过推送")
            return

        # TrendRadar 的 sender.send() 期望的是 list[str]
        if isinstance(content, list):
            messages = [str(x) for x in content if str(x).strip()]
        else:
            messages = [str(content)]

        if not messages:
            print("⚠️ Dispatcher: 无有效消息，跳过推送")
            return

        self.sender.send(messages)
        print("✅ Dispatcher: Telegram 推送完成")

    def dispatch_all(self, *args, **kwargs):
        # 兼容旧调用方式
        if args:
            return self.dispatch(args[0])
        return