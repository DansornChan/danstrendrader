# coding=utf-8
"""
通知分发调度器（Dispatcher）

负责串联：
renderer → splitter → sender
"""

from typing import Dict, Any, List

from .renderer import NotificationRenderer
from .splitter import NotificationSplitter
from .senders import TelegramSender


class NotificationDispatcher:
    def __init__(self):
        self.renderer = NotificationRenderer()
        self.splitter = NotificationSplitter()

        # 目前只启用 Telegram，后续可扩展
        self.senders = [
            TelegramSender()
        ]

    def dispatch(self, analysis_result: Dict[str, Any]):
        """
        主入口：将分析结果分发到各推送渠道
        """
        try:
            print("📦 开始渲染通知内容...")
            rendered_blocks = self.renderer.render(analysis_result)

            if not rendered_blocks:
                print("⚠️ renderer 未生成任何内容，跳过推送")
                return

            print(f"🧩 渲染完成，共 {len(rendered_blocks)} 个内容块")

            print("✂️ 开始拆分消息...")
            messages = self.splitter.split(rendered_blocks)

            if not messages:
                print("⚠️ splitter 未生成任何消息，跳过推送")
                return

            print(f"📨 拆分完成，共 {len(messages)} 条消息")

            for sender in self.senders:
                try:
                    print(f"🚀 使用 {sender.__class__.__name__} 推送中...")
                    sender.send(messages)
                except Exception as e:
                    print(f"❌ Sender {sender.__class__.__name__} 推送失败: {e}")

        except Exception as e:
            print(f"❌ NotificationDispatcher 执行失败: {e}")