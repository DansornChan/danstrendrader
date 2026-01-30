# coding=utf-8
"""
AI 客户端模块

基于 LiteLLM 的统一 AI 模型接口
支持 Gemini → DeepSeek 自动 fallback
"""

import os
from typing import Any, Dict, List

from litellm import completion


class AIClient:
    """统一的 AI 客户端（基于 LiteLLM，支持自动 fallback）"""

    def __init__(self, config: Dict[str, Any]):
        """
        config 示例：
        {
            "PRIMARY_MODEL": "gemini/gemini-2.5-pro",
            "PRIMARY_API_KEY": "...",

            "FALLBACK_MODEL": "deepseek/deepseek-chat",
            "FALLBACK_API_KEY": "...",

            "TEMPERATURE": 0.6,
            "MAX_TOKENS": 4096,
            "TIMEOUT": 120,
            "NUM_RETRIES": 2,
        }
        """

        self.primary_model = config.get(
            "PRIMARY_MODEL",
            os.getenv("PRIMARY_MODEL", "gemini/gemini-2.5-pro"),
        )
        self.primary_key = config.get(
            "PRIMARY_API_KEY",
            os.getenv("PRIMARY_API_KEY", ""),
        )

        self.fallback_model = config.get(
            "FALLBACK_MODEL",
            os.getenv("FALLBACK_MODEL", "deepseek/deepseek-chat"),
        )
        self.fallback_key = config.get(
            "FALLBACK_API_KEY",
            os.getenv("FALLBACK_API_KEY", ""),
        )

        self.temperature = config.get("TEMPERATURE", 0.6)
        self.max_tokens = config.get("MAX_TOKENS", 4096)
        self.timeout = config.get("TIMEOUT", 120)
        self.num_retries = config.get("NUM_RETRIES", 2)

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Gemini → DeepSeek 自动 fallback
        """

        models = [
            {
                "model": self.primary_model,
                "api_key": self.primary_key,
            },
            {
                "model": self.fallback_model,
                "api_key": self.fallback_key,
            },
        ]

        response = completion(
            model=models,  # ⭐ LiteLLM 原生 fallback
            messages=messages,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            timeout=kwargs.get("timeout", self.timeout),
            num_retries=kwargs.get("num_retries", self.num_retries),
        )

        return response.choices[0].message.content

    def validate_config(self) -> tuple[bool, str]:
        if not self.primary_model:
            return False, "未配置 PRIMARY_MODEL"

        if not self.primary_key:
            return False, "未配置 PRIMARY_API_KEY"

        if "/" not in self.primary_model:
            return False, f"PRIMARY_MODEL 格式错误: {self.primary_model}"

        return True, ""