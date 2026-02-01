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
        # 过滤掉空内容的消息
        valid_messages = []
        for msg in messages:
            text = msg.get("text", "").strip()
            if text:  # 只有非空内容才发送
                valid_messages.append(msg)
            else:
                print(f"[TelegramSender] 跳过空消息: key={msg.get('key')}")
        
        print(f"[TelegramSender] 准备发送 {len(valid_messages)} 条有效消息")
        
        for msg in sorted(valid_messages, key=lambda x: x.get("priority", 99)):
            text = self._decorate(msg["key"], msg["text"])
            # 确保文本非空
            if text and text.strip():
                for chunk in self._safe_split(text):
                    self._post(chunk)
            else:
                print(f"[TelegramSender] 跳过空内容: key={msg['key']}")

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
            else:
                print(f"✅ Telegram 消息发送成功")
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
        
        注意：现在renderer已经为每个块添加了标题，所以这里只添加顶层标题
        只有hot_topics需要顶层标题，其他块直接返回renderer已经添加了标题的文本
        """
        title_map = {
            "hot_topics": "🔥 **今日热点与主线**",  # 只有热点新闻需要顶层标题
            "rss_items": "",  # 空字符串，因为renderer已经添加了标题
            "standalone_data": "",  # 空字符串，因为renderer已经添加了标题
            "portfolio_impact": "",  # 空字符串，因为renderer已经添加了标题
            "ai_analysis": "",  # 空字符串，因为renderer已经添加了标题
            "trend_compare": "",  # 空字符串，因为renderer已经添加了标题
            "full_text": "📊 **完整报告**",  # 完整文本的标题
        }

        title = title_map.get(key, "")
        
        # 如果文本为空，直接返回空
        if not text or text.strip() == "":
            return ""
        
        # 如果标题为空，直接返回文本（renderer已经添加了标题）
        if not title:
            return text
        
        # 否则添加顶层标题（只针对hot_topics）
        return f"{title}\n\n{text}"