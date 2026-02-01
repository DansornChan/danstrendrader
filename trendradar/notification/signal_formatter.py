# coding=utf-8
"""
信号 / 大宗商品 Telegram 消息格式化器
用于非 AI 报告类的即时通知（强 / 中 / 弱 信号）
"""

from typing import List, Dict


def format_signal_for_telegram(signals: List[Dict]) -> List[str]:
    """
    将信号列表格式化为 Telegram 消息列表

    signals 示例：
    [
        {
            "category": "stock" | "commodity",
            "symbol": "黄金 / 原油 / 600519",
            "level": "强" | "中" | "弱",
            "direction": "看多" | "看空" | "震荡",
            "reason": "美元指数回落，避险需求上升",
            "time": "2026-02-01"
        }
    ]
    """
    messages = []

    if not signals:
        return messages

    for sig in signals:
        category = sig.get("category", "signal")
        symbol = sig.get("symbol", "未知标的")
        level = sig.get("level", "中")
        direction = sig.get("direction", "中性")
        reason = sig.get("reason", "")
        time = sig.get("time", "")

        # 不同强度使用不同 emoji
        level_emoji = {
            "强": "🚨",
            "中": "⚠️",
            "弱": "ℹ️"
        }.get(level, "📌")

        # 分类标题
        if category == "commodity":
            title = "大宗商品信号"
        elif category == "stock":
            title = "个股信号"
        else:
            title = "市场信号"

        message = (
            f"{level_emoji}【{title}｜{level}】\n"
            f"标的：{symbol}\n"
            f"方向：{direction}\n"
        )

        if reason:
            message += f"原因：{reason}\n"

        if time:
            message += f"时间：{time}"

        messages.append(message.strip())

    return messages