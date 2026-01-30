# coding=utf-8
"""
AI 客户端模块（终极稳定版）

特性：
- LiteLLM 统一接口
- Primary / Fallback 自动切换
- 明确记录实际使用模型
- Gemini quota / 429 / 400 强制 fallback
- DRY_RUN_AI 调试模式（不消耗 token）
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
    """统一 AI 客户端（LiteLLM 封装）"""

    def __init__(self, config: Dict[str, Any]):
        """
        config 示例：
        {
            "MODEL": "gemini/gemini-2.5-pro",
            "API_KEY": "...",
            "FALLBACK_MODELS": [
                {"model": "deepseek/deepseek-chat", "api_key": "..."}
            ],
            "DRY_RUN_AI": false
        }
        """

        # ===== Primary =====
        self.model: str = config.get("MODEL") or os.getenv("PRIMARY_MODEL")
        self.api_key: str = config.get("API_KEY") or os.getenv("PRIMARY_API_KEY")

        # ===== Fallback =====
        self.fallback_models: List[Dict[str, str]] = config.get(
            "FALLBACK_MODELS", []
        )

        # ===== 参数 =====
        self.temperature: float = float(config.get("TEMPERATURE", 0.7))
        self.max_tokens: int = int(config.get("MAX_TOKENS", 5000))
        self.timeout: int = int(config.get("TIMEOUT", 120))
        self.num_retries: int = int(config.get("NUM_RETRIES", 2))
        self.api_base: str = config.get("API_BASE", "")

        # ===== 调试模式 =====
        self.dry_run: bool = str(
            config.get("DRY_RUN_AI") or os.getenv("DRY_RUN_AI", "false")
        ).lower() == "true"

        self._validate()

    # ------------------------------------------------------------------

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        统一对话接口
        """

        if self.dry_run:
            logger.warning("🧪 DRY_RUN_AI=true，未调用真实模型")
            return self._dry_run_response(messages)

        params = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "timeout": kwargs.get("timeout", self.timeout),
            "num_retries": kwargs.get("num_retries", self.num_retries),
            "api_key": self.api_key,
        }

        if self.max_tokens > 0:
            params["max_tokens"] = kwargs.get("max_tokens", self.max_tokens)

        if self.api_base:
            params["api_base"] = self.api_base

        if self.fallback_models:
            params["fallbacks"] = self.fallback_models

        try:
            logger.info(f"🤖 使用 Primary 模型: {self.model}")
            response = completion(**params)
            return response.choices[0].message.content

        except (RateLimitError, BadRequestError) as e:
            logger.warning(
                f"⚠️ Primary 模型失败 ({self.model})，原因={type(e).__name__}，尝试 Fallback"
            )

            if not self.fallback_models:
                raise

            # LiteLLM 已支持 fallbacks，这里主要是兜底显示日志
            response = completion(**params)
            return response.choices[0].message.content

        except AuthenticationError as e:
            logger.error(
                f"❌ API Key 错误（{self.model}）：{str(e)}"
            )
            raise

    # ------------------------------------------------------------------

    def _dry_run_response(self, messages: List[Dict[str, str]]) -> str:
        """
        调试模式下的假返回
        """

        user_content = ""
        for m in messages:
            if m.get("role") == "user":
                user_content += m.get("content", "")[:200]

        return (
            "【DRY RUN 模式】\n"
            "未调用真实 AI 模型。\n\n"
            f"用户输入摘要：{user_content}\n\n"
            "（此结果仅用于流程调试）"
        )

    # ------------------------------------------------------------------

    def _validate(self) -> None:
        """启动前强校验"""

        if not self.model or not isinstance(self.model, str):
            raise ValueError(
                f"AI 配置错误：MODEL 必须是字符串，当前={self.model}"
            )

        if "/" not in self.model:
            raise ValueError(
                f"AI 模型格式错误：{self.model}，应为 provider/model"
            )

        if not self.api_key:
            raise ValueError("未配置 PRIMARY_API_KEY")

        if self.fallback_models:
            if not isinstance(self.fallback_models, list):
                raise ValueError("FALLBACK_MODELS 必须是 list")

            for fb in self.fallback_models:
                if not isinstance(fb, dict):
                    raise ValueError("FALLBACK_MODELS 中每一项必须是 dict")
                if "model" not in fb or "api_key" not in fb:
                    raise ValueError(
                        f"Fallback 模型配置不完整: {fb}"
                    )