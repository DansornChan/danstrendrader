# coding=utf-8
"""
Cloudflare R2 Storage Backend for TrendRadar
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

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

    def _exists(self, key: str) -> bool:
        """检查文件是否存在"""
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    # ------------------------------------------------------------------
    # StorageBackend 必须实现的接口
    # ------------------------------------------------------------------

    @property
    def supports_txt(self) -> bool:
        """R2 支持文本存储"""
        return True

    def save_news_data(self, news_data: Dict) -> bool:
        """保存爬虫新闻数据（每天一份）"""
        date = news_data.get("date") or self._today()
        key = self._key("news", f"{date}.json")
        return self._save_json(key, news_data)

    def get_latest_crawl_data(self) -> Optional[Dict]:
        """获取今天最新的爬取数据"""
        return self.load_news_by_date(self._today())
        
    def get_today_all_data(self) -> Optional[Dict]:
        """同上，获取今日数据"""
        return self.load_news_by_date(self._today())

    def is_first_crawl_today(self) -> bool:
        """检查今天是否是第一次爬取（通过检查今日数据文件是否存在）"""
        key = self._key("news", f"{self._today()}.json")
        return not self._exists(key)

    def detect_new_titles(self, current_titles: List[str]) -> List[str]:
        """
        对比已有数据，找出新标题。
        如果没有旧数据，则所有标题都视为新标题。
        """
        old_data = self.load_news_by_date(self._today())
        if not old_data:
            return current_titles
        
        # 假设 old_data 结构中有 titles 或 items 字段，这里做个通用处理
        # 实际需根据你的 news_data 结构调整
        old_titles = set()
        if "data" in old_data and isinstance(old_data["data"], dict):
            # 遍历所有源
            for source, items in old_data["data"].items():
                for item in items:
                    if isinstance(item, dict) and "title" in item:
                        old_titles.add(item["title"])
                        
        new_items = [t for t in current_titles if t not in old_titles]
        return new_items

    def save_html_report(self, date: str, html_content: str) -> bool:
        """保存 HTML 报告"""
        key = self._key("reports", f"{date}.html")
        try:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=html_content.encode("utf-8"),
                ContentType="text/html",
            )
            return True
        except Exception as e:
            print(f"R2 save_html_report failed: {e}")
            return False

    def save_txt_snapshot(self, date: str, txt_content: str) -> bool:
        """保存文本快照"""
        key = self._key("snapshots", f"{date}.txt")
        try:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=txt_content.encode("utf-8"),
                ContentType="text/plain",
            )
            return True
        except Exception as e:
            print(f"R2 save_txt_snapshot failed: {e}")
            return False

    # --- 推送记录相关 ---

    def has_pushed_today(self) -> bool:
        """检查今天是否已经执行过推送"""
        key = self._key("pushed_flags", f"{self._today()}.json")
        return self._exists(key)

    def record_push(self, status: str = "success") -> bool:
        """记录今天已推送"""
        key = self._key("pushed_flags", f"{self._today()}.json")
        data = {
            "pushed_at": datetime.utcnow().isoformat(),
            "status": status
        }
        return self._save_json(key, data)

    # --- 清理相关 ---

    def cleanup(self) -> None:
        """清理入口"""
        self.apply_retention()

    def cleanup_old_data(self) -> None:
        """清理旧数据的别名"""
        self.apply_retention()

    # ------------------------------------------------------------------
    # 内部/辅助方法 (复用及实现细节)
    # ------------------------------------------------------------------

    def _save_json(self, key: str, data: Any) -> bool:
        try:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=json.dumps(data, ensure_ascii=False).encode("utf-8"),
                ContentType="application/json",
            )
            return True
        except Exception as e:
            print(f"R2 save error ({key}): {e}")
            return False

    def load_news_by_date(self, date: str) -> Optional[Dict]:
        key = self._key("news", f"{date}.json")
        try:
            resp = self.s3.get_object(Bucket=self.bucket, Key=key)
            return json.loads(resp["Body"].read().decode("utf-8"))
        except Exception:
            return None

    def save_ai_result(self, date: str, ai_result: Dict) -> bool:
        key = self._key("ai", f"{date}.json")
        payload = {
            "date": date,
            "saved_at": datetime.utcnow().isoformat(),
            "result": ai_result,
        }
        return self._save_json(key, payload)

    def load_ai_result(self, date: str) -> Optional[Dict]:
        key = self._key("ai", f"{date}.json")
        try:
            resp = self.s3.get_object(Bucket=self.bucket, Key=key)
            return json.loads(resp["Body"].read().decode("utf-8"))
        except Exception:
            return None

    def list_dates(self, category: str) -> List[str]:
        prefix = self._key(category)
        paginator = self.s3.get_paginator("list_objects_v2")
        dates = []
        # 处理分页，以防文件过多
        try:
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    # 获取文件名并去掉扩展名
                    name = obj["Key"].split("/")[-1]
                    if name.endswith(".json"):
                        dates.append(name.replace(".json", ""))
            return sorted(set(dates))
        except Exception:
            return []

    def apply_retention(self) -> None:
        if self.retention_days <= 0:
            return
        
        cutoff = datetime.utcnow() - timedelta(days=self.retention_days)
        paginator = self.s3.get_paginator("list_objects_v2")
        
        try:
            # 遍历整个 prefix 下的文件
            for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix):
                for obj in page.get("Contents", []):
                    # 检查 LastModified
                    if obj["LastModified"].replace(tzinfo=None) < cutoff:
                        print(f"Removing old file: {obj['Key']}")
                        self.s3.delete_object(Bucket=self.bucket, Key=obj['Key'])
        except Exception as e:
            print(f"Retention cleanup failed: {e}")

    # RSS 兼容 (可保持为空或简单实现)
    def save_rss_data(self, rss_data) -> bool:
        return True

    def detect_new_rss_items(self, rss_data):
        return None

    def get_latest_rss_data(self, date: str):
        return None

    def get_rss_data(self, date: str):
        return None
