# coding=utf-8
"""
消息发送模块（Senders）

负责将 splitter 拆分后的消息发送到不同平台
"""

import os
import requests
from abc import ABC, abstractmethod
from typing import List, Dict


# =========================
# 抽象基类
# =========================
class BaseSender(ABC):
    @abstractmethod
    def send(self, messages: List[Dict[str, str]]):
        pass


# =========================
# Telegram Sender
# =========================
class TelegramSender(BaseSender):
    TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
    MAX_LENGTH = 4096

    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not self.token or not self.chat_id:
            raise RuntimeError(
                "Telegram 配置缺失：请检查 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID"
            )

    # =========================
    # 主入口
    # =========================
    def send(self, messages: List[Dict[str, str]]):
        """
        messages: splitter 输出的消息列表
        """
        # 过滤空消息
        valid_messages = []
        for msg in messages:
            text = msg.get("text", "")
            if text and text.strip():
                valid_messages.append(msg)
            else:
                print(f"[TelegramSender] 跳过空消息: key={msg.get('key')}")

        print(f"[TelegramSender] 准备发送 {len(valid_messages)} 条消息")

        # 按 priority 顺序发送
        for msg in sorted(valid_messages, key=lambda x: x.get("priority", 99)):
            key = msg.get("key")
            raw_text = msg.get("text", "")

            text = self._decorate(key, raw_text)
            if not text:
                continue

            # ===== 关键规则 =====
            # AI 分析、完整报告：只允许 splitter 拆，sender 不再二次拆
            if key in {"ai_analysis", "full_text"}:
                self._post(text)
                continue

            # 其他类型：允许 sender 按段落安全拆分
            for chunk in self._safe_split_plain(text):
                self._post(chunk)

    # =========================
    # 实际发送
    # =========================
    def _post(self, text: str):
        if not text or not text.strip():
            return

        url = self.TELEGRAM_API.format(token=self.token)
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code != 200:
                print(f"⚠️ Telegram 推送失败: {resp.text}")
            else:
                print("✅ Telegram 消息发送成功")
        except Exception as e:
            print(f"❌ Telegram 推送异常: {e}")

    # =========================
    # 非 AI 内容的安全拆分
    # =========================
    def _safe_split_plain(self, text: str) -> List[str]:
        """
        仅用于非 AI 内容（如热点、RSS、独立数据区）
        按“段落”拆分，避免 Markdown 被截断
        """
        chunks: List[str] = []
        current = ""

        paragraphs = text.split("\n\n")
        for p in paragraphs:
            if len(current) + len(p) + 2 > self.MAX_LENGTH:
                if current.strip():
                    chunks.append(current.strip())
                current = p + "\n\n"
            else:
                current += p + "\n\n"

        if current.strip():
            chunks.append(current.strip())

        return chunks

    # =========================
    # 顶层标题装饰
    # =========================
    def _decorate(self, key: str, text: str) -> str:
        """
        renderer 已经为各模块生成了内部标题
        sender 只在必要时加“顶层标题”
        """
        title_map = {
            "hot_topics": "🔥 **今日热点与主线**",
            "full_text": "📊 **完整报告**",
        }

        title = title_map.get(key, "")
        if not title:
            return text

        return f"{title}\n\n{text}"