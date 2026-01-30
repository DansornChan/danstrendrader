# coding=utf-8
"""
AI 客户端模块

基于 LiteLLM 的统一 AI 模型接口
支持 Gemini / DeepSeek 自动 fallback
"""

import os
from typing import Any, Dict, List

from litellm import completion


class AIClient:
    """统一的 AI 客户端（基于 LiteLLM）"""

    def __init__(self, config: Dict[str, Any]):
        """
        config 示例：
        {
            "PRIMARY_MODEL": "gemini/gemini-1.5-pro",
            "PRIMARY_API_KEY": "...",

            "FALLBACK_MODEL": "deepseek/deepseek-chat",
            "FALLBACK_API_KEY": "...",

            "TEMPERATURE": 0.7,
            "MAX_TOKENS": 5000,
            "TIMEOUT": 120,
        }
        """

        self.primary_model = config.get("PRIMARY_MODEL") or os.getenv("PRIMARY_MODEL")
        self.primary_key = config.get("PRIMARY_API_KEY") or os.getenv("PRIMARY_API_KEY")

        self.fallback_model = config.get("FALLBACK_MODEL") or os.getenv("FALLBACK_MODEL")
        self.fallback_key = config.get("FALLBACK_API_KEY") or os.getenv("FALLBACK_API_KEY")

        self.temperature = config.get("TEMPERATURE", 0.7)
        self.max_tokens = config.get("MAX_TOKENS", 5000)
        self.timeout = config.get("TIMEOUT", 120)

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Gemini → DeepSeek 自动 fallback
        """

        models = []

        if self.primary_model and self.primary_key:
            models.append({
                "model": self.primary_model,
                "api_key": self.primary_key,
            })

        if self.fallback_model and self.fallback_key:
            models.append({
                "model": self.fallback_model,
                "api_key": self.fallback_key,
            })

        if not models:
            raise RuntimeError("未配置任何可用的 AI 模型")

        response = completion(
            model=models,
            messages=messages,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            timeout=kwargs.get("timeout", self.timeout),
        )

        return response.choices[0].message.content

    def validate_config(self) -> tuple[bool, str]:
        if not self.primary_model:
            return False, "未配置 PRIMARY_MODEL"

        if not self.primary_key:
            return False, "未配置 PRIMARY_API_KEY"

        return True, ""