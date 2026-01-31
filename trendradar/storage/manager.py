# coding=utf-8
import os
import logging
from typing import Optional, Dict

from trendradar.storage.local import LocalStorageBackend

# ----------------------------------------------------------------------
# 初始化日志记录器
# ----------------------------------------------------------------------
logger = logging.getLogger(__name__)

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


class StorageManager:
    """
    存储管理器（Facade）

    - 负责选择 backend
    - 统一对外暴露存储接口
    - 自动从环境变量加载缺失的配置
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
        
        # --------------------------------------------------------------
        # 智能配置加载逻辑
        # --------------------------------------------------------------
        self.remote_config = remote_config or {}
        if not self.remote_config:
            self.remote_config = self._load_config_from_env()

        self.local_retention_days = local_retention_days
        self.remote_retention_days = remote_retention_days
        self.pull_enabled = pull_enabled
        self.pull_days = pull_days
        self.timezone = timezone

        self.backend_name: str = "unknown"
        self._backend = None

    # ------------------------------------------------------------------
    # 辅助：从环境变量构建配置
    # ------------------------------------------------------------------

    def _load_config_from_env(self) -> Dict[str, str]:
        """
        当 remote_config 为空时，尝试从系统环境变量自动补全
        支持 S3_前缀, R2_前缀 等常见命名
        """
        config = {}
        
        # 定义需要查找的字段及其对应的环境变量候选项
        env_mapping = {
            "ENDPOINT_URL": ["S3_ENDPOINT_URL", "R2_ENDPOINT_URL", "STORAGE_ENDPOINT"],
            "BUCKET_NAME": ["S3_BUCKET_NAME", "R2_BUCKET_NAME", "STORAGE_BUCKET"],
            "ACCESS_KEY_ID": ["S3_ACCESS_KEY_ID", "R2_ACCESS_KEY_ID", "AWS_ACCESS_KEY_ID"],
            "SECRET_ACCESS_KEY": ["S3_SECRET_ACCESS_KEY", "R2_SECRET_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY"],
            "PREFIX": ["S3_PREFIX", "R2_PREFIX", "STORAGE_PREFIX"],
            "RETENTION_DAYS": ["S3_RETENTION_DAYS", "R2_RETENTION_DAYS", "RETENTION_DAYS"]
        }

        for config_key, env_candidates in env_mapping.items():
            for env_var in env_candidates:
                val = os.getenv(env_var)
                if val:
                    config[config_key] = val
                    break
        
        return config

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

        # 构造通用参数
        common_kwargs = {
            "config": self.remote_config,
            "retention_days": self.remote_retention_days,
            "pull_enabled": self.pull_enabled,
            "pull_days": self.pull_days,
            "timezone": self.timezone,
        }

        if backend_type == "r2":
            if not HAS_R2:
                raise RuntimeError("R2StorageBackend 不可用 (缺少依赖或文件)")
            self.backend_name = "r2"
            return R2StorageBackend(**common_kwargs)

        if backend_type == "remote":
            if not HAS_REMOTE:
                raise RuntimeError("RemoteStorageBackend 不可用")
            self.backend_name = "remote"
            return RemoteStorageBackend(**common_kwargs)

        if backend_type == "auto":
            if self._is_github_actions():
                # 优先尝试 R2
                if HAS_R2 and self._has_valid_remote_config():
                    self.backend_name = "r2"
                    return R2StorageBackend(**common_kwargs)
                
                # 其次尝试通用 Remote
                if HAS_REMOTE and self._has_valid_remote_config():
                    self.backend_name = "remote"
                    return RemoteStorageBackend(**common_kwargs)

            # 默认 fallback 到本地
            self.backend_name = "local"
            return LocalStorageBackend(
                data_dir=self.data_dir,
                enable_txt=self.enable_txt,
                enable_html=self.enable_html,
                retention_days=self.local_retention_days,
                timezone=self.timezone,
            )

        raise ValueError(f"未知 backend_type: {backend_type}")
    
    def _has_valid_remote_config(self) -> bool:
        """简单的预检查：配置是否看起来可用"""
        return bool(self.remote_config.get("ENDPOINT_URL") or self.remote_config.get("S3_ENDPOINT_URL")) \
           and bool(self.remote_config.get("BUCKET_NAME") or self.remote_config.get("S3_BUCKET_NAME"))

    # ------------------------------------------------------------------
    # Backend 懒加载
    # ------------------------------------------------------------------

    @property
    def backend(self):
        if self._backend is None:
            self._backend = self._select_backend()
            # 确保 logger 存在
            if 'logger' in globals():
                logger.info(f"[Storage] 实际使用后端: {self.backend_name}")
            else:
                print(f"[Storage] 实际使用后端: {self.backend_name}")
        return self._backend

    # ------------------------------------------------------------------
    # 方法代理 (Facade)
    # ------------------------------------------------------------------

    def save_news_data(self, *args, **kwargs):
        return self.backend.save_news_data(*args, **kwargs)

    def cleanup_old_data(self, *args, **kwargs):
        return self.backend.cleanup_old_data(*args, **kwargs)

    def pull_recent_data(self, *args, **kwargs):
        if hasattr(self.backend, "pull_recent_data"):
            return self.backend.pull_recent_data(*args, **kwargs)
        return None

    def __getattr__(self, item):
        backend = object.__getattribute__(self, "backend")
        if hasattr(backend, item):
            return getattr(backend, item)
        raise AttributeError(f"'StorageManager' object has no attribute '{item}'")


# ----------------------------------------------------------------------
# 工厂方法
# ----------------------------------------------------------------------

def get_storage_manager(**kwargs) -> StorageManager:
    return StorageManager(**kwargs)
