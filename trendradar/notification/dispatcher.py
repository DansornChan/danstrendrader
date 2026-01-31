# coding=utf-8
"""
通知分发调度器（Dispatcher）

负责串联：
renderer → splitter → sender
"""

from typing import Any, List, Dict

from trendradar.notification.senders import TelegramSender
from trendradar.notification.renderer import NotificationRenderer
from trendradar.notification.splitter import NotificationSplitter


class NotificationDispatcher:
    def __init__(self, *args, **kwargs):
        """
        兼容旧版调用：
        - NotificationDispatcher()
        - NotificationDispatcher(config=xxx)
        """
        self.config = kwargs.get("config")

        self.renderer = NotificationRenderer()
        self.splitter = NotificationSplitter()
        self.sender = TelegramSender()

    def dispatch(self, analysis_result: Any):
        """
        主入口：将分析结果分发到各推送渠道
        """
        try:
            print("📦 Dispatcher: 开始渲染通知内容")
            rendered_blocks = self.renderer.render(analysis_result)

            if not rendered_blocks:
                print("⚠️ Dispatcher: renderer 未生成内容，跳过推送")
                return

            print(f"🧩 Dispatcher: 渲染完成，共 {len(rendered_blocks)} 个 block")

            print("✂️ Dispatcher: 开始拆分消息")
            messages: List[Dict[str, str]] = self.splitter.split(rendered_blocks)

            if not messages:
                print("⚠️ Dispatcher: splitter 未生成消息，跳过推送")
                return

            print(f"📨 Dispatcher: 拆分完成，共 {len(messages)} 条消息")

            self.sender.send(messages)
            print("✅ Dispatcher: Telegram 推送完成")

        except Exception as e:
            print(f"❌ Dispatcher 执行失败: {e}")