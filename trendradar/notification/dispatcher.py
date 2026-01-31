# coding=utf-8
"""
通知分发调度器（Dispatcher）

负责串联：
renderer → splitter → sender

⚠️ 这是一个兼容实现：
- 兼容 NotificationDispatcher()
- 兼容 NotificationDispatcher(config=xxx)
- 不阻断主流程
"""

from typing import Any, Dict


class NotificationDispatcher:
    def __init__(self, *args, **kwargs):
        """
        兼容不同版本调用方式
        """
        self.config = kwargs.get("config", {}) or {}

    def dispatch(self, *args, **kwargs):
        """
        主入口：将分析结果分发到各推送渠道

        当前版本为安全兜底实现：
        - 不做复杂调度
        - 不抛异常
        - 保证主流程继续执行
        """
        try:
            # Dispatcher 在当前仓库中不是强依赖
            # 真正的推送逻辑在 send_to_xxx 中完成
            return
        except Exception as e:
            print(f"❌ NotificationDispatcher 执行失败: {e}")