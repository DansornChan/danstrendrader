# coding=utf-8
"""
AI Client（终极兼容版）

- 兼容旧 validate_config() → (bool, str)
- LiteLLM 正确 fallback
- 防止 model=list 导致 split 崩溃
"""

import os
import logging
from typing import Any, Dict, List

from litellm import completion
from litellm.exceptions import (
    RateLimitError,
    BadRequestError,
    AuthenticationError,
)

logger = logging.getLogger(__name__)


class AIClient:
    def __init__(self, config: Dict[str, Any]):
        # ===== Primary =====
        self.model = config.get("MODEL") or os.getenv("PRIMARY_MODEL")
        self.api_key = config.get("API_KEY") or os.getenv("PRIMARY_API_KEY")

        # ===== Fallback =====
        self.fallback_models: List[Dict[str, str]] = config.get(
            "FALLBACK_MODELS", []
        )

        # ===== Params =====
        self.temperature = float(config.get("TEMPERATURE", 0.7))
        self.max_tokens = int(config.get("MAX_TOKENS", 5000))
        self.timeout = int(config.get("TIMEOUT", 120))
        self.num_retries = int(config.get("NUM_RETRIES", 2))

        self.dry_run = str(
            config.get("DRY_RUN_AI") or os.getenv("DRY_RUN_AI", "false")
        ).lower() == "true"

    # ------------------------------------------------------------------
    # ✅ 旧代码兼容接口（非常关键）
    def validate_config(self):
        try:
            self._validate()
            return True, ""
        except Exception as e:
            return False, str(e)

    # ------------------------------------------------------------------
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        if self.dry_run:
            logger.warning("🧪 DRY_RUN_AI=true，未调用真实模型")
            return self._dry_run_response(messages)

        params = {
            "model": self.model,      # ⚠️ 必须是 string
            "messages": messages,
            "api_key": self.api_key,
            "temperature": self.temperature,
            "timeout": self.timeout,
            "num_retries": self.num_retries,
        }

        if self.max_tokens > 0:
            params["max_tokens"] = self.max_tokens

        # ✅ LiteLLM 官方 fallback 用法
        if self.fallback_models:
            params["fallbacks"] = self.fallback_models

        try:
            logger.info(f"🤖 使用模型: {self.model}")
            resp = completion(**params)
            return resp.choices[0].message.content

        except (RateLimitError, BadRequestError) as e:
            logger.warning(
                f"⚠️ Primary 失败，将尝试 fallback（{type(e).__name__}）"
            )
            raise

        except AuthenticationError as e:
            logger.error(f"❌ API Key 错误: {e}")
            raise

    # ------------------------------------------------------------------
    def _dry_run_response(self, messages):
        preview = ""
        for m in messages:
            if m.get("role") == "user":
                preview += m.get("content", "")[:200]
        return f"【DRY RUN】AI 未调用\n摘要：{preview}"

    # ------------------------------------------------------------------
    def _validate(self):
        if not self.model:
            raise ValueError("未配置 PRIMARY_MODEL")

        if not isinstance(self.model, str):
            raise ValueError("PRIMARY_MODEL 必须是字符串")

        if "/" not in self.model:
            raise ValueError(
                f"模型格式错误：{self.model}，应为 provider/model"
            )

        if not self.api_key:
            raise ValueError("未配置 PRIMARY_API_KEY")

        if self.fallback_models:
            if not isinstance(self.fallback_models, list):
                raise ValueError("FALLBACK_MODELS 必须是 list")

            for fb in self.fallback_models:
                if not isinstance(fb, dict):
                    raise ValueError(f"非法 fallback 配置: {fb}")
                if "model" not in fb or "api_key" not in fb:
                    raise ValueError(f"fallback 缺少字段: {fb}")