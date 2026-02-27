#!/usr/bin/env python3
"""从 txt 清单同步 RSS feeds 到 config/config.yaml。"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List

import yaml


def _read_lines(file_path: Path) -> List[str]:
    if not file_path.exists():
        return []
    return [line.strip() for line in file_path.read_text(encoding="utf-8").splitlines()]


def _safe_id(raw: str) -> str:
    lowered = raw.strip().lower()
    normalized = re.sub(r"[^a-z0-9\-]+", "-", lowered)
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return normalized or "rss-item"


def _parse_base_rss(file_path: Path) -> List[Dict[str, str]]:
    feeds: List[Dict[str, str]] = []
    for line in _read_lines(file_path):
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 3:
            print(f"[跳过] 无法解析（需要 id|name|url）：{line}")
            continue
        feed_id, name, url = parts
        if not url.startswith(("http://", "https://")):
            print(f"[跳过] URL 非法：{url}")
            continue
        feeds.append({"id": _safe_id(feed_id), "name": name, "url": url})
    return feeds


def _parse_google_alerts(file_path: Path) -> List[Dict[str, str]]:
    feeds: List[Dict[str, str]] = []
    for line in _read_lines(file_path):
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|", 1)]
        if len(parts) != 2:
            print(f"[跳过] 无法解析（需要 关键词|url）：{line}")
            continue
        keyword, url = parts
        if not url.startswith(("http://", "https://")):
            print(f"[跳过] URL 非法：{url}")
            continue
        feeds.append(
            {
                "id": f"google-alert-{_safe_id(keyword)}",
                "name": f"Google Alerts - {keyword}",
                "url": url,
            }
        )
    return feeds


def _dedupe_by_url(feeds: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    deduped = []
    for feed in feeds:
        url = feed["url"].strip()
        if url in seen:
            continue
        seen.add(url)
        deduped.append(feed)
    return deduped


def sync_rss_config(config_path: Path, rss_list_path: Path, google_alerts_path: Path, dry_run: bool) -> int:
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    config_data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    base_feeds = _parse_base_rss(rss_list_path)
    google_feeds = _parse_google_alerts(google_alerts_path)
    merged_feeds = _dedupe_by_url(base_feeds + google_feeds)

    if "rss" not in config_data or not isinstance(config_data.get("rss"), dict):
        config_data["rss"] = {}
    config_data["rss"]["feeds"] = merged_feeds

    print(f"[同步] 基础源: {len(base_feeds)}")
    print(f"[同步] Google Alerts 源: {len(google_feeds)}")
    print(f"[同步] 合并后 RSS 源: {len(merged_feeds)}")

    if dry_run:
        print("[DRY-RUN] 未写入 config.yaml")
        return len(merged_feeds)

    config_path.write_text(
        yaml.safe_dump(config_data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"[完成] 已更新: {config_path}")
    return len(merged_feeds)


def main() -> None:
    parser = argparse.ArgumentParser(description="同步 RSS 清单到 config.yaml")
    parser.add_argument("--config", default="config/config.yaml", help="config.yaml 路径")
    parser.add_argument("--rss-list", default="config/rss_list.txt", help="基础 RSS 列表文件")
    parser.add_argument(
        "--google-alerts",
        default="config/Googlealerts_RSS.txt",
        help="Google Alerts RSS 列表文件",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不写入")
    args = parser.parse_args()

    sync_rss_config(
        config_path=Path(args.config),
        rss_list_path=Path(args.rss_list),
        google_alerts_path=Path(args.google_alerts),
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
