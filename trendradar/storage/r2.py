# coding=utf-8
"""
Cloudflare R2 Storage Backend for TrendRadar
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

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
    
    def _yesterday(self) -> str:
        return (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

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
    # 新实现的抽象方法
    # ------------------------------------------------------------------

    def cleanup(self) -> bool:
        """
        清理临时数据或过期数据
        """
        try:
            self.apply_retention()
            return True
        except Exception:
            return False

    def cleanup_old_data(self) -> bool:
        """
        清理旧数据
        """
        return self.cleanup()

    def detect_new_titles(self, current_titles: List[str], source: str = "") -> List[str]:
        """
        检测新标题
        """
        # 获取昨天的数据进行比较
        yesterday_data = self.load_news_by_date(self._yesterday())
        if not yesterday_data:
            return current_titles  # 如果没有昨天数据，所有都是新的
        
        # 提取昨天的标题
        yesterday_titles = []
        for item in yesterday_data.get("data", []):
            if isinstance(item, dict) and "title" in item:
                yesterday_titles.append(item["title"])
        
        # 找出不在昨天标题中的新标题
        new_titles = [title for title in current_titles if title not in yesterday_titles]
        return new_titles

    def get_latest_crawl_data(self) -> Optional[Dict]:
        """
        获取最新的爬虫数据
        """
        # 获取所有日期
        dates = self.list_dates("news")
        if not dates:
            return None
        
        # 返回最新日期的数据
        latest_date = dates[-1]
        return self.load_news_by_date(latest_date)

    def get_today_all_data(self) -> Optional[Dict]:
        """
        获取今天的所有数据
        """
        return self.load_news_by_date(self._today())

    def has_pushed_today(self) -> bool:
        """
        检查今天是否已经推送过
        """
        # 检查是否存在推送记录文件
        push_key = self._key("push", f"{self._today()}.json")
        try:
            self.s3.head_object(Bucket=self.bucket, Key=push_key)
            return True
        except Exception:
            return False

    def is_first_crawl_today(self) -> bool:
        """
        检查是否是今天的第一次爬取
        """
        # 检查今天是否已经有数据文件
        news_key = self._key("news", f"{self._today()}.json")
        try:
            self.s3.head_object(Bucket=self.bucket, Key=news_key)
            return False  # 文件存在，不是第一次
        except Exception:
            return True  # 文件不存在，是第一次

    def record_push(self, push_data: Dict) -> bool:
        """
        记录推送信息
        """
        date = push_data.get("date", self._today())
        key = self._key("push", f"{date}.json")
        
        # 添加时间戳
        push_data["pushed_at"] = datetime.utcnow().isoformat()
        
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(push_data, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )
        return True

    def save_html_report(self, html_content: str, filename: str) -> bool:
        """
        保存HTML报告
        """
        key = self._key("reports", filename)
        
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=html_content.encode("utf-8"),
            ContentType="text/html",
        )
        return True

    def save_txt_snapshot(self, txt_content: str, filename: str) -> bool:
        """
        保存文本快照
        """
        key = self._key("snapshots", filename)
        
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=txt_content.encode("utf-8"),
            ContentType="text/plain",
        )
        return True

    def supports_txt(self) -> bool:
        """
        是否支持文本快照
        """
        return True

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