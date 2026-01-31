# coding=utf-8
import os
import logging
from typing import Optional

from trendradar.storage import (
    LocalStorageBackend,
    RemoteStorageBackend,
    R2StorageBackend,
    HAS_REMOTE,
    HAS_R2,
)

logger = logging.getLogger(__name__)


class StorageManager:
    """
    存储管理器
    """

    def __init__(
        self,
        backend_type: str = "auto",
        data_dir: str = "output",
        enable_txt: bool = True,
        enable_html: bool = True,
        remote_config: Optional[dict] = None,
        local_retention_days: int = 0,
        remote_retention_days: int = 0,
        pull_enabled: bool = False,
        pull_days: int = 0,
        timezone: str = "Asia/Shanghai",
    ):
        self.backend_type = backend_type
        self.data_dir = data_dir
        self.enable_txt = enable_txt
        self.enable_html = enable_html
        self.remote_config = remote_config or {}
        self.local_retention_days = local_retention_days
        self.remote_retention_days = remote_retention_days
        self.pull_enabled = pull_enabled
        self.pull_days = pull_days
        self.timezone = timezone

        self._backend = None
        self._remote_backend = None

    # ------------------------------------------------------------------
    # 后端选择逻辑
    # ------------------------------------------------------------------

    def _is_github_actions(self) -> bool:
        return os.getenv("GITHUB_ACTIONS") == "true"

    def _select_backend(self):
        """
        根据 backend_type 和运行环境选择后端
        """
        backend_type = (self.backend_type or "auto").lower()

        # 1️⃣ 强制 r2
        if backend_type == "r2":
            if not HAS_R2:
                raise RuntimeError("R2StorageBackend 不可用，请确认 r2.py 与依赖已安装")
            logger.info("[Storage] 使用 Cloudflare R2 后端")
            return R2StorageBackend(
                config=self.remote_config,
                retention_days=self.remote_retention_days,
                pull_enabled=self.pull_enabled,
                pull_days=self.pull_days,
                timezone=self.timezone,
            )

        # 2️⃣ 强制 remote（S3 兼容）
        if backend_type == "remote":
            if not HAS_REMOTE:
                raise RuntimeError("RemoteStorageBackend 不可用，请确认 boto3 已安装")
            logger.info("[Storage] 使用通用 Remote(S3) 后端")
            return RemoteStorageBackend(
                config=self.remote_config,
                retention_days=self.remote_retention_days,
                pull_enabled=self.pull_enabled,
                pull_days=self.pull_days,
                timezone=self.timezone,
            )

        # 3️⃣ 自动选择
        if backend_type == "auto":
            # GitHub Actions：优先 R2
            if self._is_github_actions():
                if HAS_R2:
                    logger.info("[Storage] GitHub Actions 检测到，自动使用 R2")
                    return R2StorageBackend(
                        config=self.remote_config,
                        retention_days=self.remote_retention_days,
                        pull_enabled=self.pull_enabled,
                        pull_days=self.pull_days,
                        timezone=self.timezone,
                    )
                if HAS_REMOTE:
                    logger.info("[Storage] GitHub Actions 检测到，使用 Remote(S3)")
                    return RemoteStorageBackend(
                        config=self.remote_config,
                        retention_days=self.remote_retention_days,
                        pull_enabled=self.pull_enabled,
                        pull_days=self.pull_days,
                        timezone=self.timezone,
                    )

            # 本地 or 兜底
            logger.info("[Storage] 使用本地 LocalStorage 后端")
            return LocalStorageBackend(
                data_dir=self.data_dir,
                enable_txt=self.enable_txt,
                enable_html=self.enable_html,
                retention_days=self.local_retention_days,
                timezone=self.timezone,
            )

        raise ValueError(f"未知 backend_type: {backend_type}")

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------

    @property
    def backend(self):
        if self._backend is None:
            self._backend = self._select_backend()
        return self._backend


# ----------------------------------------------------------------------
# 便捷函数
# ----------------------------------------------------------------------

def get_storage_manager(**kwargs) -> StorageManager:
    return StorageManager(**kwargs)