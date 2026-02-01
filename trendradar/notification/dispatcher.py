# coding=utf-8
"""
通知分发调度器（Dispatcher）
兼容 TrendRadar v4 / v5
支持：
- AI / 报告类通知（renderer → splitter → sender）
- 信号 / 大宗商品即时通知（signal_formatter → sender）
"""

from .renderer import NotificationRenderer
from .splitter import NotificationSplitter
from .senders import TelegramSender
from .signal_formatter import format_signal_for_telegram


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
        统一分发入口
        - AI 报告 / 日报 / 周报 → renderer
        - signals → signal_formatter（直发）
        """
        final_data = {}

        # 1. analysis_result
        if analysis_result is not None:
            if isinstance(analysis_result, dict):
                final_data.update(analysis_result)
            else:
                final_data["analysis_result"] = analysis_result

        # 2. report_data
        if report_data is not None:
            final_data["report_data"] = report_data

        # 3. 其他参数
        for key in [
            "ai_analysis",
            "rss_items",
            "rss_new_items",
            "standalone_data",
            "portfolio",
            "history_summary",
            "mode",
            "update_info",
            "signals",  # ⭐ 新增
        ]:
            if key in kwargs:
                final_data[key] = kwargs[key]

        # 4. 新格式 report_data 直接覆盖
        if isinstance(report_data, dict):
            if "stats" in report_data and "rss_items" in report_data:
                final_data = report_data
            elif "report_data" in report_data:
                final_data = report_data

        print(f"[Dispatcher] 最终数据键: {list(final_data.keys())}")

        # ==============================
        # ⭐ 信号 / 大宗商品 → 直发通道
        # ==============================
        if "signals" in final_data:
            print("📊 检测到 signals，使用 signal formatter")
            try:
                messages = format_signal_for_telegram(final_data["signals"])
                if messages:
                    self.sender.send(messages)
                    print("✅ Signal Telegram 推送完成")
                else:
                    print("⚠️ signals 为空，未发送")
            except Exception as e:
                print(f"❌ Signal 推送失败: {e}")
            return  # ❗ 不再进入 AI 报告流程

        # ==============================
        # 默认：AI / 报告类流程
        # ==============================
        self._dispatch_impl(final_data)

    def _dispatch_impl(self, analysis_result):
        try:
            print("📦 开始生成 Telegram 通知（报告模式）...")

            blocks = self.renderer.render(analysis_result)
            if not blocks:
                print("⚠️ 没有生成任何通知内容")
                return

            print("[Dispatcher] 渲染后的内容块:")
            for key, content in blocks.items():
                if content and content.strip():
                    preview = content[:100] + "..." if len(content) > 100 else content
                    print(f"  - {key}: {preview}")
                else:
                    print(f"  - {key}: [空内容]")

            messages = self.splitter.split(blocks)
            if not messages:
                print("⚠️ 拆分后无消息")
                return

            self.sender.send(messages)
            print("✅ Telegram 推送完成（报告模式）")

        except Exception as e:
            print(f"❌ Telegram 推送失败: {e}")