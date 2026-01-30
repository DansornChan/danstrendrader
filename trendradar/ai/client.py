# coding=utf-8
"""
AI Client（稳定兼容版）

- LiteLLM Primary / Fallback 正确用法
- 兼容旧 validate_config() 调用
- 防止 model 被错误传为 list
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
        self.model: str = config.get("MODEL") or os.getenv("PRIMARY_MODEL")
        self.api_key: str = config.get("API_KEY") or os.getenv("PRIMARY_API_KEY")

        # ===== Fallback（一定是 list）=====
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

        self._validate()

    # ------------------------------------------------------------------

    # ✅ 兼容旧代码（不要删）
    def validate_config(self):
        self._validate()

    # ------------------------------------------------------------------

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        if self.dry_run:
            logger.warning("🧪 DRY_RUN_AI=true，未调用真实模型")
            return self._dry_run_response(messages)

        params = {
            "model": self.model,               # ⚠️ 必须是 string
            "messages": messages,
            "api_key": self.api_key,
            "temperature": self.temperature,
            "timeout": self.timeout,
            "num_retries": self.num_retries,
        }

        if self.max_tokens > 0:
            params["max_tokens"] = self.max_tokens

        # ✅ LiteLLM 正确 fallback 方式
        if self.fallback_models:
            params["fallbacks"] = self.fallback_models

        try:
            logger.info(f"🤖 Primary 模型: {self.model}")
            resp = completion(**params)
            return resp.choices[0].message.content

        except (RateLimitError, BadRequestError) as e:
            logger.warning(
                f"⚠️ Primary 失败，错误={type(e).__name__}，LiteLLM 将自动尝试 fallback"
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

        return (
            "【DRY RUN】未调用真实模型\n\n"
            f"用户输入摘要：{preview}"
        )

    # ------------------------------------------------------------------

    def _validate(self):
        if not isinstance(self.model, str):
            raise ValueError(
                f"PRIMARY_MODEL 必须是字符串，当前={self.model}"
            )

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