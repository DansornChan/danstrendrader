# coding=utf-8
import os
import logging
from typing import Optional

from trendradar.storage.local import LocalStorageBackend

# ----------------------------------------------------------------------
# 可选 Remote(S3) 后端
# ----------------------------------------------------------------------
try:
    from trendradar.storage.remote import RemoteStorageBackend
    HAS_REMOTE = True
except ImportError:
    RemoteStorageBackend = None
    HAS_REMOTE = False

# ----------------------------------------------------------------------
# 可选 Cloudflare R2 后端
# ----------------------------------------------------------------------
try:
    from trendradar.storage.r2 import R2StorageBackend
    HAS_R2 = True
except ImportError:
    R2StorageBackend = None
    HAS_R2 = False

logger = logging.getLogger(__name__)


class StorageManager:
    """
    存储管理器（Facade）

    - 负责选择 backend
    - 统一对外暴露存储接口
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

        self.backend_name: str = "unknown"
        self._backend = None

    # ------------------------------------------------------------------
    # 环境判断
    # ------------------------------------------------------------------

    def _is_github_actions(self) -> bool:
        return os.getenv("GITHUB_ACTIONS") == "true"

    # ------------------------------------------------------------------
    # 后端选择
    # ------------------------------------------------------------------

    def _select_backend(self):
        backend_type = (self.backend_type or "auto").lower()

        if backend_type == "r2":
            if not HAS_R2:
                raise RuntimeError("R2StorageBackend 不可用")
            self.backend_name = "r2"
            return R2StorageBackend(
                config=self.remote_config,
                retention_days=self.remote_retention_days,
                pull_enabled=self.pull_enabled,
                pull_days=self.pull_days,
                timezone=self.timezone,
            )

        if backend_type == "remote":
            if not HAS_REMOTE:
                raise RuntimeError("RemoteStorageBackend 不可用")
            self.backend_name = "remote"
            return RemoteStorageBackend(
                config=self.remote_config,
                retention_days=self.remote_retention_days,
                pull_enabled=self.pull_enabled,
                pull_days=self.pull_days,
                timezone=self.timezone,
            )

        if backend_type == "auto":
            if self._is_github_actions():
                if HAS_R2:
                    self.backend_name = "r2"
                    return R2StorageBackend(
                        config=self.remote_config,
                        retention_days=self.remote_retention_days,
                        pull_enabled=self.pull_enabled,
                        pull_days=self.pull_days,
                        timezone=self.timezone,
                    )
                if HAS_REMOTE:
                    self.backend_name = "remote"
                    return RemoteStorageBackend(
                        config=self.remote_config,
                        retention_days=self.remote_retention_days,
                        pull_enabled=self.pull_enabled,
                        pull_days=self.pull_days,
                        timezone=self.timezone,
                    )

            self.backend_name = "local"
            return LocalStorageBackend(
                data_dir=self.data_dir,
                enable_txt=self.enable_txt,
                enable_html=self.enable_html,
                retention_days=self.local_retention_days,
                timezone=self.timezone,
            )

        raise ValueError(f"未知 backend_type: {backend_type}")

    # ------------------------------------------------------------------
    # Backend 懒加载
    # ------------------------------------------------------------------

    @property
    def backend(self):
        if self._backend is None:
            self._backend = self._select_backend()
            logger.info(f"[Storage] 实际使用后端: {self.backend_name}")
        return self._backend

    # ------------------------------------------------------------------
    # 🔥 关键：方法代理（Facade 核心）
    # ------------------------------------------------------------------

    def save_news_data(self, *args, **kwargs):
        return self.backend.save_news_data(*args, **kwargs)

    def cleanup_old_data(self, *args, **kwargs):
        return self.backend.cleanup_old_data(*args, **kwargs)

    def pull_recent_data(self, *args, **kwargs):
        if hasattr(self.backend, "pull_recent_data"):
            return self.backend.pull_recent_data(*args, **kwargs)

    def __getattr__(self, item):
        """
        兜底代理：backend 有的方法，manager 自动透传
        """
        backend = object.__getattribute__(self, "backend")
        if hasattr(backend, item):
            return getattr(backend, item)
        raise AttributeError(f"'StorageManager' object has no attribute '{item}'")


# ----------------------------------------------------------------------
# 工厂方法
# ----------------------------------------------------------------------

def get_storage_manager(**kwargs) -> StorageManager:
    return StorageManager(**kwargs)