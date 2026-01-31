# coding=utf-8
"""
通知分发调度器（Dispatcher）
兼容 TrendRadar v4 / v5
"""

from .renderer import NotificationRenderer
from .splitter import NotificationSplitter
from .senders import TelegramSender


class NotificationDispatcher:
    def __init__(self, *args, **kwargs):
        """
        兼容所有调用方式
        """
        report_type = kwargs.get("report_type", "current")

        self.renderer = NotificationRenderer(report_type=report_type)
        self.splitter = NotificationSplitter()
        self.sender = TelegramSender()

    def dispatch(self, analysis_result):
        self._dispatch_impl(analysis_result)

    def dispatch_all(self, analysis_result=None, report_data=None, **kwargs):
        """
        兼容旧代码：同时支持传入 analysis_result 或 report_data
        """
        # 优先使用 analysis_result，如果没有则使用 report_data
        # 这里的逻辑是：不管外部传进来叫什么名字，最终都统一传给 _dispatch_impl
        final_data = analysis_result if analysis_result is not None else report_data
        
        if final_data is None:
            print("⚠️ dispatch_all 被调用，但未收到有效的数据 (analysis_result 或 report_data 均为空)")
            return

        self._dispatch_impl(final_data)


    def _dispatch_impl(self, analysis_result):
        try:
            print("📦 开始生成 Telegram 通知...")

            blocks = self.renderer.render(analysis_result)
            if not blocks:
                print("⚠️ 没有生成任何通知内容")
                return

            messages = self.splitter.split(blocks)
            if not messages:
                print("⚠️ 拆分后无消息")
                return

            self.sender.send(messages)
            print("✅ Telegram 推送完成")

        except Exception as e:
            print(f"❌ Telegram 推送失败: {e}")