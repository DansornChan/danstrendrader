# coding=utf-8
"""
Cloudflare R2 Storage Backend for TrendRadar
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import boto3
from botocore.client import Config

from trendradar.storage.base import StorageBackend


class R2StorageBackend(StorageBackend):
    backend_name = "cloudflare-r2"

    def __init__(self, config: Dict):
        """
        config 示例:
        {
            "ENDPOINT_URL": "https://xxxxx.r2.cloudflarestorage.com",
            "BUCKET_NAME": "trendradar",
            "ACCESS_KEY_ID": "...",
            "SECRET_ACCESS_KEY": "...",
            "PREFIX": "trendradar",
            "RETENTION_DAYS": 30
        }
        """
        self.endpoint_url = config.get("ENDPOINT_URL")
        self.bucket = config.get("BUCKET_NAME")
        self.access_key = config.get("ACCESS_KEY_ID")
        self.secret_key = config.get("SECRET_ACCESS_KEY")
        self.prefix = config.get("PREFIX", "trendradar").strip("/")
        self.retention_days = int(config.get("RETENTION_DAYS", 0))

        if not all([self.endpoint_url, self.bucket, self.access_key, self.secret_key]):
            raise ValueError("R2 存储配置不完整")

        self.s3 = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

    # ------------------------------------------------------------------
    # 基础工具
    # ------------------------------------------------------------------

    def _key(self, *parts: str) -> str:
        return f"{self.prefix}/" + "/".join(p.strip("/") for p in parts)

    def _today(self) -> str:
        return datetime.utcnow().strftime("%Y-%m-%d")

    # ------------------------------------------------------------------
    # 新闻数据
    # ------------------------------------------------------------------

    def save_news_data(self, news_data: Dict) -> bool:
        """
        保存爬虫新闻数据（每天一份）
        """
        date = news_data.get("date") or self._today()
        key = self._key("news", f"{date}.json")

        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(news_data, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )
        return True

    def load_news_by_date(self, date: str) -> Optional[Dict]:
        key = self._key("news", f"{date}.json")
        try:
            resp = self.s3.get_object(Bucket=self.bucket, Key=key)
            return json.loads(resp["Body"].read().decode("utf-8"))
        except Exception:
            return None

    # ------------------------------------------------------------------
    # AI 分析结果
    # ------------------------------------------------------------------

    def save_ai_result(self, date: str, ai_result: Dict) -> bool:
        """
        保存 AI 分析结果（结构化 or 文本）
        """
        key = self._key("ai", f"{date}.json")

        payload = {
            "date": date,
            "saved_at": datetime.utcnow().isoformat(),
            "result": ai_result,
        }

        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )
        return True

    def load_ai_result(self, date: str) -> Optional[Dict]:
        key = self._key("ai", f"{date}.json")
        try:
            resp = self.s3.get_object(Bucket=self.bucket, Key=key)
            return json.loads(resp["Body"].read().decode("utf-8"))
        except Exception:
            return None

    # ------------------------------------------------------------------
    # 历史 & retention
    # ------------------------------------------------------------------

    def list_dates(self, category: str) -> List[str]:
        """
        category: news / ai
        """
        prefix = self._key(category)
        paginator = self.s3.get_paginator("list_objects_v2")

        dates = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                name = obj["Key"].split("/")[-1]
                if name.endswith(".json"):
                    dates.append(name.replace(".json", ""))

        return sorted(set(dates))

    def apply_retention(self) -> None:
        """
        根据 RETENTION_DAYS 自动清理旧数据
        """
        if self.retention_days <= 0:
            return

        cutoff = datetime.utcnow() - timedelta(days=self.retention_days)

        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix):
            for obj in page.get("Contents", []):
                if obj["LastModified"].replace(tzinfo=None) < cutoff:
                    self.s3.delete_object(
                        Bucket=self.bucket,
                        Key=obj["Key"],
                    )

    # ------------------------------------------------------------------
    # StorageBackend 接口兼容
    # ------------------------------------------------------------------

    def save_rss_data(self, rss_data) -> bool:
        """
        RSS 数据目前不强制持久化，可按需扩展
        """
        return True

    def detect_new_rss_items(self, rss_data):
        return None

    def get_latest_rss_data(self, date: str):
        return None

    def get_rss_data(self, date: str):
        return None