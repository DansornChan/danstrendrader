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

        # 更新ordered_keys，包含所有可能的键
        ordered_keys = [
            "hot_topics",
            "rss_items",           # 新增RSS新闻
            "standalone_data",     # 新增独立展示区
            "ai_analysis",
            "portfolio_impact",
            "trend_compare",
        ]

        priority = 1
        for key in ordered_keys:
            text = rendered.get(key)
            if not text or not text.strip():
                # 打印调试信息
                print(f"[Splitter] 跳过空内容或缺失的键: {key}")
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

        # 打印拆分结果
        print(f"[Splitter] 拆分完成，生成 {len(messages)} 条消息")
        for msg in messages:
            print(f"[Splitter] 消息: key={msg['key']}, priority={msg['priority']}, 长度={len(msg['text'])}")

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