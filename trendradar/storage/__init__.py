# coding=utf-8
"""
存储模块 - 支持多种存储后端
"""

# ------------------------------------------------------------
# 基础类型 & 数据结构（最底层，绝不能反向依赖）
# ------------------------------------------------------------
from trendradar.storage.base import (
    StorageBackend,
    NewsItem,
    NewsData,
    RSSItem,
    RSSData,
    convert_crawl_results_to_news_data,
    convert_news_data_to_results,
)

# ------------------------------------------------------------
# Mixin
# ------------------------------------------------------------
from trendradar.storage.sqlite_mixin import SQLiteStorageMixin

# ------------------------------------------------------------
# 本地后端（稳定依赖）
# ------------------------------------------------------------
from trendradar.storage.local import LocalStorageBackend

# ------------------------------------------------------------
# 远程后端（S3 / R2 / OSS 等）
# ------------------------------------------------------------
HAS_REMOTE = False
HAS_R2 = False

RemoteStorageBackend = None
R2StorageBackend = None

try:
    from trendradar.storage.remote import RemoteStorageBackend
    HAS_REMOTE = True
except ImportError:
    pass

try:
    from trendradar.storage.r2 import R2StorageBackend
    HAS_R2 = True
except ImportError:
    pass

# ------------------------------------------------------------
# 管理器（最后导入，防止循环）
# ------------------------------------------------------------
from trendradar.storage.manager import (
    StorageManager,
    get_storage_manager,
)

__all__ = [
    # 基础类
    "StorageBackend",
    "NewsItem",
    "NewsData",
    "RSSItem",
    "RSSData",

    # Mixin
    "SQLiteStorageMixin",

    # 转换函数
    "convert_crawl_results_to_news_data",
    "convert_news_data_to_results",

    # 后端
    "LocalStorageBackend",
    "RemoteStorageBackend",
    "R2StorageBackend",

    # 能力标记
    "HAS_REMOTE",
    "HAS_R2",

    # 管理器
    "StorageManager",
    "get_storage_manager",
]