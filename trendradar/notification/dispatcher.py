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
        现在支持从 kwargs 中提取所有需要的参数
        """
        # 构建一个完整的数据字典，包含所有参数
        final_data = {}
        
        # 1. 如果有 analysis_result，使用它（可能是完整数据）
        if analysis_result is not None:
            if isinstance(analysis_result, dict):
                final_data.update(analysis_result)
            else:
                # 如果是其他类型，尝试转换为字典
                final_data['analysis_result'] = analysis_result
        
        # 2. 如果有 report_data，作为 report_data 键
        if report_data is not None:
            final_data['report_data'] = report_data
        
        # 3. 从 kwargs 中提取其他关键参数
        for key in ['ai_analysis', 'rss_items', 'rss_new_items', 
                   'standalone_data', 'portfolio', 'history_summary',
                   'mode', 'update_info']:
            if key in kwargs:
                final_data[key] = kwargs[key]
        
        # 4. 如果 report_data 已经是一个包含所有数据的字典（新格式）
        if isinstance(report_data, dict):
            # 检查 report_data 是否已经包含了我们需要的数据
            if 'stats' in report_data and 'rss_items' in report_data:
                # 这已经是完整数据，直接使用
                final_data = report_data
            elif 'report_data' in report_data:
                # 如果 report_data 中包含 report_data 键，提取它
                final_data = report_data
        
        # 调试信息
        print(f"[Dispatcher] 最终数据键: {list(final_data.keys())}")
        if 'rss_items' in final_data:
            rss_count = len(final_data['rss_items']) if isinstance(final_data['rss_items'], list) else 0
            print(f"[Dispatcher] RSS项目数: {rss_count}")
        
        self._dispatch_impl(final_data)

    def _dispatch_impl(self, analysis_result):
        try:
            print("📦 开始生成 Telegram 通知...")

            blocks = self.renderer.render(analysis_result)
            if not blocks:
                print("⚠️ 没有生成任何通知内容")
                return

            # 调试：打印每个块的预览
            print(f"[Dispatcher] 渲染后的内容块:")
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
            print("✅ Telegram 推送完成")

        except Exception as e:
            print(f"❌ Telegram 推送失败: {e}")