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
            raise RuntimeError("Telegram 配置缺失：请检查 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")

    def send(self, messages: List[Dict[str, str]]):
        for msg in sorted(messages, key=lambda x: x.get("priority", 99)):
            text = self._decorate(msg["key"], msg["text"])
            for chunk in self._safe_split(text):
                self._post(chunk)

    # =========================
    # 私有方法
    # =========================
    def _post(self, text: str):
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
        except Exception as e:
            print(f"❌ Telegram 推送异常: {e}")

    def _safe_split(self, text: str):
        """
        避免超过 Telegram 4096 字符限制
        """
        chunks = []
        while len(text) > self.MAX_LENGTH:
            split_pos = text.rfind("\n", 0, self.MAX_LENGTH)
            if split_pos == -1:
                split_pos = self.MAX_LENGTH
            chunks.append(text[:split_pos])
            text = text[split_pos:]
        chunks.append(text)
        return chunks

    def _decorate(self, key: str, text: str) -> str:
        """
        根据消息类型加标题
        """
        title_map = {
            "hot_topics": "🔥 **今日热点与主线**",
            "portfolio_impact": "📊 **持仓相关影响分析**",
            "ai_analysis": "🤖 **AI 综合研判**",
            "trend_compare": "📈 **趋势对比与演化**",
        }

        title = title_map.get(key)
        if title:
            return f"{title}\n\n{text}"

        return text