# coding=utf-8
"""
通知内容拆分器（Splitter）

原则：
- AI 分析属于强语义整体，默认不拆
- 其他模块允许按长度拆分
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

        # 哪些 key 绝对不允许被拆
        self.atomic_keys = {
            "ai_analysis",
        }

    def split(self, rendered: Dict[str, str]) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = []

        if not self.enable_multi_message:
            return [{
                "key": "full",
                "text": rendered.get("full_text", ""),
                "priority": 1,
            }]

        ordered_keys = [
            "hot_topics",
            "rss_items",
            "standalone_data",
            "ai_analysis",
            "portfolio_impact",
            "trend_compare",
        ]

        priority = 1

        for key in ordered_keys:
            text = rendered.get(key)
            if not text or not text.strip():
                print(f"[Splitter] 跳过空内容: {key}")
                continue

            text = text.strip()

            # ===== 原子内容：不拆 =====
            if key in self.atomic_keys:
                messages.append({
                    "key": key,
                    "text": text,
                    "priority": priority,
                })
                priority += 1
                continue

            # ===== 普通内容：按长度拆 =====
            if len(text) <= self.max_length:
                messages.append({
                    "key": key,
                    "text": text,
                    "priority": priority,
                })
            else:
                messages.extend(
                    self._split_long_text(key, text, priority)
                )

            priority += 1

        print(f"[Splitter] 拆分完成，共 {len(messages)} 条消息")
        for msg in messages:
            print(
                f"[Splitter] key={msg['key']} "
                f"priority={msg['priority']} "
                f"length={len(msg['text'])}"
            )

        return messages

    # =========================
    # 普通文本安全拆分（段落级）
    # =========================
    def _split_long_text(
        self,
        key: str,
        text: str,
        priority: int,
    ) -> List[Dict[str, str]]:
        chunks: List[Dict[str, str]] = []
        current = ""

        # 按“空行”作为段落拆，避免破坏语义
        paragraphs = text.split("\n\n")

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current) + len(para) + 2 > self.max_length:
                if current.strip():
                    chunks.append({
                        "key": key,
                        "text": current.strip(),
                        "priority": priority,
                    })
                current = para + "\n\n"
            else:
                current += para + "\n\n"

        if current.strip():
            chunks.append({
                "key": key,
                "text": current.strip(),
                "priority": priority,
            })

        return chunks