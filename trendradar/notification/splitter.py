# coding=utf-8
"""
通知内容拆分器（Splitter）

职责：
- 将 renderer 输出的结构化文本，拆分为多条消息
- 决定发送顺序、是否合并
"""

from typing import Dict, List


class NotificationSplitter:
    def __init__(
        self,
        max_length: int = 3500,
        enable_multi_message: bool = True,
    ):
        self.max_length = max_length
        self.enable_multi_message = enable_multi_message

    def split(self, rendered: Dict[str, str]) -> List[Dict[str, str]]:
        """
        rendered: renderer.render(...) 返回的 dict
        """
        messages = []

        if not self.enable_multi_message:
            return [{
                "key": "full",
                "text": rendered.get("full_text", ""),
            }]

        ordered_keys = [
            "hot_topics",
            "portfolio_impact",
            "ai_analysis",
            "trend_compare",
        ]

        priority = 1
        for key in ordered_keys:
            text = rendered.get(key)
            if not text:
                continue

            if len(text) <= self.max_length:
                messages.append({
                    "key": key,
                    "text": text,
                    "priority": priority,
                })
            else:
                # 超长兜底拆分
                messages.extend(
                    self._split_long_text(key, text, priority)
                )

            priority += 1

        return messages

    # =========================
    # 长文本安全拆分
    # =========================
    def _split_long_text(
        self,
        key: str,
        text: str,
        priority: int,
    ) -> List[Dict[str, str]]:
        chunks = []
        current = ""

        for line in text.splitlines():
            if len(current) + len(line) + 1 > self.max_length:
                chunks.append({
                    "key": key,
                    "text": current.strip(),
                    "priority": priority,
                })
                current = line + "\n"
            else:
                current += line + "\n"

        if current.strip():
            chunks.append({
                "key": key,
                "text": current.strip(),
                "priority": priority,
            })

        return chunks