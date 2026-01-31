# coding=utf-8
"""
极简 NotificationDispatcher
只负责：把 TrendRadar 生成的文本推送到 Telegram
"""

import os
from trendradar.notification.senders import TelegramSender


class NotificationDispatcher:
    def __init__(self, *args, **kwargs):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not self.bot_token or not self.chat_id:
            raise RuntimeError("❌ Telegram 环境变量未配置")

        self.sender = TelegramSender(
            bot_token=self.bot_token,
            chat_id=self.chat_id,
        )

    def dispatch(self, content, *args, **kwargs):
        """
        content: TrendRadar 生成的字符串 / dict / list
        """
        print("📨 Dispatcher: 开始发送 Telegram 消息")

        if isinstance(content, dict):
            text = content.get("full_text") or str(content)
        else:
            text = str(content)

        if not text.strip():
            print("⚠️ Dispatcher: 内容为空，跳过推送")
            return

        self.sender.send([text])
        print("✅ Dispatcher: Telegram 推送完成")

    def dispatch_all(self, *args, **kwargs):
        """
        兼容旧版本调用
        """
        # TrendRadar 通常把最终内容作为第一个参数传入
        if args:
            return self.dispatch(args[0])
        return