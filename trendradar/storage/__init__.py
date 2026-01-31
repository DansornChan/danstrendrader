# coding=utf-8
"""
存储模块 - 支持多种存储后端

支持的存储后端:
- local: 本地 SQLite + TXT/HTML 文件
- remote: 远程云存储（S3 兼容协议：R2/OSS/COS/S3 等）
- r2: Cloudflare R2（remote 的具体实现之一）
- auto: 根据环境自动选择（GitHub Actions 用 remote，其他用 local）
"""

from trendradar.storage.base import (
    StorageBackend,
    NewsItem,
    NewsData,
    RSSItem,
    RSSData,
    convert_crawl_results_to_news_data,
    convert_news_data_to_results,
)
from trendradar.storage.sqlite_mixin import SQLiteStorageMixin
from trendradar.storage.local import LocalStorageBackend
from trendradar.storage.manager import StorageManager, get_storage_manager

# ----------------------------------------------------------------------
# 远程后端（S3 兼容）
# ----------------------------------------------------------------------

# Remote（通用 S3）
try:
    from trendradar.storage.remote import RemoteStorageBackend
    HAS_REMOTE = True
except ImportError:
    RemoteStorageBackend = None
    HAS_REMOTE = False

# Cloudflare R2（明确区分，避免你以后 OSS / COS 混在一起）
try:
    from trendradar.storage.r2 import R2StorageBackend
    HAS_R2 = True
except ImportError:
    R2StorageBackend = None
    HAS_R2 = False

__all__ = [
    # ------------------------------------------------------------------
    # 基础类
    # ------------------------------------------------------------------
    "StorageBackend",
    "NewsItem",
    "NewsData",
    "RSSItem",
    "RSSData",

    # ------------------------------------------------------------------
    # Mixin
    # ------------------------------------------------------------------
    "SQLiteStorageMixin",

    # ------------------------------------------------------------------
    # 转换函数
    # ------------------------------------------------------------------
    "convert_crawl_results_to_news_data",
    "convert_news_data_to_results",

    # ------------------------------------------------------------------
    # 后端实现
    # ------------------------------------------------------------------
    "LocalStorageBackend",
    "RemoteStorageBackend",
    "R2StorageBackend",

    # 能力标记
    "HAS_REMOTE",
    "HAS_R2",

    # ------------------------------------------------------------------
    # 管理器
    # ------------------------------------------------------------------
    "StorageManager",
    "get_storage_manager",
]