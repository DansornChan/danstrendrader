# coding=utf-8
"""
消息发送器模块

将报告数据发送到各种通知渠道：
- 飞书 (Feishu/Lark)
- 钉钉 (DingTalk)
- 企业微信 (WeCom/WeWork)
- Telegram
- 邮件 (Email)
- ntfy
- Bark
- Slack

每个发送函数都支持分批发送，并通过参数化配置实现与 CONFIG 的解耦。
"""

import smtplib
import time
import json
import textwrap  # [新增] 用于文本切片
from datetime import datetime
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

import requests

from .batch import add_batch_headers, get_max_batch_header_size
from .formatters import convert_markdown_to_mrkdwn, strip_markdown


def _render_ai_analysis(ai_analysis: Any, channel: str) -> str:
    """渲染 AI 分析内容为指定渠道格式"""
    if not ai_analysis:
        return ""

    try:
        from trendradar.ai.formatter import get_ai_analysis_renderer
        renderer = get_ai_analysis_renderer(channel)
        return renderer(ai_analysis)
    except ImportError:
        return ""


# === SMTP 邮件配置 ===
SMTP_CONFIGS = {
    # Gmail（使用 STARTTLS）
    "gmail.com": {"server": "smtp.gmail.com", "port": 587, "encryption": "TLS"},
    # QQ邮箱（使用 SSL，更稳定）
    "qq.com": {"server": "smtp.qq.com", "port": 465, "encryption": "SSL"},
    # Outlook（使用 STARTTLS）
    "outlook.com": {"server": "smtp-mail.outlook.com", "port": 587, "encryption": "TLS"},
    "hotmail.com": {"server": "smtp-mail.outlook.com", "port": 587, "encryption": "TLS"},
    "live.com": {"server": "smtp-mail.outlook.com", "port": 587, "encryption": "TLS"},
    # 网易邮箱（使用 SSL，更稳定）
    "163.com": {"server": "smtp.163.com", "port": 465, "encryption": "SSL"},
    "126.com": {"server": "smtp.126.com", "port": 465, "encryption": "SSL"},
    # 新浪邮箱（使用 SSL）
    "sina.com": {"server": "smtp.sina.com", "port": 465, "encryption": "SSL"},
    # 搜狐邮箱（使用 SSL）
    "sohu.com": {"server": "smtp.sohu.com", "port": 465, "encryption": "SSL"},
    # 天翼邮箱（使用 SSL）
    "189.cn": {"server": "smtp.189.cn", "port": 465, "encryption": "SSL"},
    # 阿里云邮箱（使用 TLS）
    "aliyun.com": {"server": "smtp.aliyun.com", "port": 465, "encryption": "TLS"},
    # Yandex邮箱（使用 TLS）
    "yandex.com": {"server": "smtp.yandex.com", "port": 465, "encryption": "TLS"},
    # iCloud邮箱（使用 SSL）
    "icloud.com": {"server": "smtp.mail.me.com", "port": 587, "encryption": "SSL"},
}


def send_to_feishu(
    webhook_url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    account_label: str = "",
    *,
    batch_size: int = 29000,
    batch_interval: float = 1.0,
    split_content_func: Callable = None,
    get_time_func: Callable = None,
    rss_items: Optional[list] = None,
    rss_new_items: Optional[list] = None,
    ai_analysis: Any = None,
    display_regions: Optional[Dict] = None,
    standalone_data: Optional[Dict] = None,
) -> bool:
    """
    发送到飞书
    """
    headers = {"Content-Type": "application/json"}
    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    log_prefix = f"飞书{account_label}" if account_label else "飞书"

    ai_content = None
    ai_stats = None
    if ai_analysis:
        ai_content = _render_ai_analysis(ai_analysis, "feishu")
        if getattr(ai_analysis, "success", False):
            ai_stats = {
                "total_news": getattr(ai_analysis, "total_news", 0),
                "analyzed_news": getattr(ai_analysis, "analyzed_news", 0),
                "max_news_limit": getattr(ai_analysis, "max_news_limit", 0),
                "hotlist_count": getattr(ai_analysis, "hotlist_count", 0),
                "rss_count": getattr(ai_analysis, "rss_count", 0),
            }

    header_reserve = get_max_batch_header_size("feishu")
    batches = split_content_func(
        report_data,
        "feishu",
        update_info,
        max_bytes=batch_size - header_reserve,
        mode=mode,
        rss_items=rss_items,
        rss_new_items=rss_new_items,
        ai_content=ai_content,
        standalone_data=standalone_data,
        ai_stats=ai_stats,
        report_type=report_type,
    )

    batches = add_batch_headers(batches, "feishu", batch_size)
    print(f"{log_prefix}消息分为 {len(batches)} 批次发送 [{report_type}]")

    for i, batch_content in enumerate(batches, 1):
        content_size = len(batch_content.encode("utf-8"))
        print(f"发送{log_prefix}第 {i}/{len(batches)} 批次，大小：{content_size} 字节 [{report_type}]")

        payload = {
            "msg_type": "text",
            "content": {"text": batch_content},
        }

        try:
            response = requests.post(
                webhook_url, headers=headers, json=payload, proxies=proxies, timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("StatusCode") == 0 or result.get("code") == 0:
                    print(f"{log_prefix}第 {i}/{len(batches)} 批次发送成功 [{report_type}]")
                    if i < len(batches):
                        time.sleep(batch_interval)
                else:
                    error_msg = result.get("msg") or result.get("StatusMessage", "未知错误")
                    print(f"{log_prefix}第 {i}/{len(batches)} 批次发送失败 [{report_type}]，错误：{error_msg}")
                    return False
            else:
                print(f"{log_prefix}第 {i}/{len(batches)} 批次发送失败 [{report_type}]，状态码：{response.status_code}")
                return False
        except Exception as e:
            print(f"{log_prefix}第 {i}/{len(batches)} 批次发送出错 [{report_type}]：{e}")
            return False

    print(f"{log_prefix}所有 {len(batches)} 批次发送完成 [{report_type}]")
    return True


def send_to_dingtalk(
    webhook_url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    account_label: str = "",
    *,
    batch_size: int = 20000,
    batch_interval: float = 1.0,
    split_content_func: Callable = None,
    rss_items: Optional[list] = None,
    rss_new_items: Optional[list] = None,
    ai_analysis: Any = None,
    display_regions: Optional[Dict] = None,
    standalone_data: Optional[Dict] = None,
) -> bool:
    """
    发送到钉钉
    """
    headers = {"Content-Type": "application/json"}
    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    log_prefix = f"钉钉{account_label}" if account_label else "钉钉"

    ai_content = None
    ai_stats = None
    if ai_analysis:
        ai_content = _render_ai_analysis(ai_analysis, "dingtalk")
        if getattr(ai_analysis, "success", False):
            ai_stats = {
                "total_news": getattr(ai_analysis, "total_news", 0),
                "analyzed_news": getattr(ai_analysis, "analyzed_news", 0),
                "max_news_limit": getattr(ai_analysis, "max_news_limit", 0),
                "hotlist_count": getattr(ai_analysis, "hotlist_count", 0),
                "rss_count": getattr(ai_analysis, "rss_count", 0),
            }

    header_reserve = get_max_batch_header_size("dingtalk")
    batches = split_content_func(
        report_data,
        "dingtalk",
        update_info,
        max_bytes=batch_size - header_reserve,
        mode=mode,
        rss_items=rss_items,
        rss_new_items=rss_new_items,
        ai_content=ai_content,
        standalone_data=standalone_data,
        ai_stats=ai_stats,
        report_type=report_type,
    )

    batches = add_batch_headers(batches, "dingtalk", batch_size)
    print(f"{log_prefix}消息分为 {len(batches)} 批次发送 [{report_type}]")

    for i, batch_content in enumerate(batches, 1):
        content_size = len(batch_content.encode("utf-8"))
        print(f"发送{log_prefix}第 {i}/{len(batches)} 批次，大小：{content_size} 字节 [{report_type}]")

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": f"TrendRadar 热点分析报告 - {report_type}",
                "text": batch_content,
            },
        }

        try:
            response = requests.post(
                webhook_url, headers=headers, json=payload, proxies=proxies, timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    print(f"{log_prefix}第 {i}/{len(batches)} 批次发送成功 [{report_type}]")
                    if i < len(batches):
                        time.sleep(batch_interval)
                else:
                    print(f"{log_prefix}第 {i}/{len(batches)} 批次发送失败 [{report_type}]，错误：{result.get('errmsg')}")
                    return False
            else:
                print(f"{log_prefix}第 {i}/{len(batches)} 批次发送失败 [{report_type}]，状态码：{response.status_code}")
                return False
        except Exception as e:
            print(f"{log_prefix}第 {i}/{len(batches)} 批次发送出错 [{report_type}]：{e}")
            return False

    print(f"{log_prefix}所有 {len(batches)} 批次发送完成 [{report_type}]")
    return True


def send_to_wework(
    webhook_url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    account_label: str = "",
    *,
    batch_size: int = 4000,
    batch_interval: float = 1.0,
    msg_type: str = "markdown",
    split_content_func: Callable = None,
    rss_items: Optional[list] = None,
    rss_new_items: Optional[list] = None,
    ai_analysis: Any = None,
    display_regions: Optional[Dict] = None,
    standalone_data: Optional[Dict] = None,
) -> bool:
    """
    发送到企业微信
    """
    headers = {"Content-Type": "application/json"}
    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    log_prefix = f"企业微信{account_label}" if account_label else "企业微信"
    is_text_mode = msg_type.lower() == "text"
    header_format_type = "wework_text" if is_text_mode else "wework"

    ai_content = None
    ai_stats = None
    if ai_analysis:
        ai_content = _render_ai_analysis(ai_analysis, "wework")
        if getattr(ai_analysis, "success", False):
            ai_stats = {
                "total_news": getattr(ai_analysis, "total_news", 0),
                "analyzed_news": getattr(ai_analysis, "analyzed_news", 0),
                "max_news_limit": getattr(ai_analysis, "max_news_limit", 0),
                "hotlist_count": getattr(ai_analysis, "hotlist_count", 0),
                "rss_count": getattr(ai_analysis, "rss_count", 0),
            }

    header_reserve = get_max_batch_header_size(header_format_type)
    batches = split_content_func(
        report_data, "wework", update_info, max_bytes=batch_size - header_reserve, mode=mode,
        rss_items=rss_items,
        rss_new_items=rss_new_items,
        ai_content=ai_content,
        standalone_data=standalone_data,
        ai_stats=ai_stats,
        report_type=report_type,
    )

    batches = add_batch_headers(batches, header_format_type, batch_size)
    print(f"{log_prefix}消息分为 {len(batches)} 批次发送 [{report_type}]")

    for i, batch_content in enumerate(batches, 1):
        if is_text_mode:
            plain_content = strip_markdown(batch_content)
            payload = {"msgtype": "text", "text": {"content": plain_content}}
            content_size = len(plain_content.encode("utf-8"))
        else:
            payload = {"msgtype": "markdown", "markdown": {"content": batch_content}}
            content_size = len(batch_content.encode("utf-8"))

        print(f"发送{log_prefix}第 {i}/{len(batches)} 批次，大小：{content_size} 字节 [{report_type}]")

        try:
            response = requests.post(
                webhook_url, headers=headers, json=payload, proxies=proxies, timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    print(f"{log_prefix}第 {i}/{len(batches)} 批次发送成功 [{report_type}]")
                    if i < len(batches):
                        time.sleep(batch_interval)
                else:
                    print(f"{log_prefix}第 {i}/{len(batches)} 批次发送失败 [{report_type}]，错误：{result.get('errmsg')}")
                    return False
            else:
                print(f"{log_prefix}第 {i}/{len(batches)} 批次发送失败 [{report_type}]，状态码：{response.status_code}")
                return False
        except Exception as e:
            print(f"{log_prefix}第 {i}/{len(batches)} 批次发送出错 [{report_type}]：{e}")
            return False

    print(f"{log_prefix}所有 {len(batches)} 批次发送完成 [{report_type}]")
    return True


def send_to_telegram(
    bot_token: str,
    chat_id: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    account_label: str = "",
    *,
    batch_size: int = 4000,
    batch_interval: float = 1.0,
    split_content_func: Callable = None,
    rss_items: Optional[list] = None,
    rss_new_items: Optional[list] = None,
    ai_analysis: Any = None,
    display_regions: Optional[Dict] = None,
    standalone_data: Optional[Dict] = None,
) -> bool:
    """
    发送到 Telegram（修复 AI 长文本截断问题）
    """
    headers = {"Content-Type": "application/json"}
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    log_prefix = f"Telegram{account_label}" if account_label else "Telegram"

    # 1. 渲染 AI 内容
    ai_content = None
    ai_stats = None
    if ai_analysis:
        ai_content = _render_ai_analysis(ai_analysis, "telegram")
        if getattr(ai_analysis, "success", False):
            ai_stats = {
                "total_news": getattr(ai_analysis, "total_news", 0),
                "analyzed_news": getattr(ai_analysis, "analyzed_news", 0),
                "max_news_limit": getattr(ai_analysis, "max_news_limit", 0),
                "hotlist_count": getattr(ai_analysis, "hotlist_count", 0),
                "rss_count": getattr(ai_analysis, "rss_count", 0),
            }

    # 2. 初始切分
    header_reserve = get_max_batch_header_size("telegram")
    initial_batches = split_content_func(
        report_data, 
        "telegram", 
        update_info, 
        max_bytes=batch_size - header_reserve, 
        mode=mode,
        rss_items=rss_items,
        rss_new_items=rss_new_items,
        ai_content=ai_content, # [修复] 传入 AI 内容
        standalone_data=standalone_data,
        ai_stats=ai_stats,
        report_type=report_type,
    )

    # 3. [增强修复] 强制二次切分：如果单个 batch 依然超过 Telegram 限制（例如 AI 长文）
    # Telegram 硬限制是 4096 字符，我们设定安全阈值 4000
    SAFE_LIMIT = 4000
    final_batches = []
    
    for batch in initial_batches:
        if len(batch) <= SAFE_LIMIT:
            final_batches.append(batch)
        else:
            # 强制按长度切断
            print(f"{log_prefix}检测到超长消息块 ({len(batch)} 字符)，进行强制二次切分...")
            chunks = textwrap.wrap(batch, SAFE_LIMIT, break_long_words=False, replace_whitespace=False)
            final_batches.extend(chunks)

    # 4. 添加批次头部
    final_batches = add_batch_headers(final_batches, "telegram", batch_size)

    print(f"{log_prefix}消息分为 {len(final_batches)} 批次发送 [{report_type}]")

    # 5. 逐批发送
    for i, batch_content in enumerate(final_batches, 1):
        content_size = len(batch_content.encode("utf-8"))
        print(f"发送{log_prefix}第 {i}/{len(final_batches)} 批次，大小：{content_size} 字节 [{report_type}]")

        payload = {
            "chat_id": chat_id,
            "text": batch_content,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            response = requests.post(
                url, headers=headers, json=payload, proxies=proxies, timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    print(f"{log_prefix}第 {i}/{len(final_batches)} 批次发送成功 [{report_type}]")
                    if i < len(final_batches):
                        time.sleep(batch_interval)
                else:
                    print(f"{log_prefix}第 {i}/{len(final_batches)} 批次发送失败 [{report_type}]，错误：{result.get('description')}")
                    # 如果是因为消息太长，尝试用普通文本再发一次（放弃 HTML 格式）
                    if "message is too long" in str(result.get('description')).lower():
                         print(f"{log_prefix}尝试以降级模式（纯文本）重发该批次...")
                         payload["parse_mode"] = None
                         requests.post(url, headers=headers, json=payload, proxies=proxies, timeout=30)
            else:
                print(f"{log_prefix}第 {i}/{len(final_batches)} 批次发送失败 [{report_type}]，状态码：{response.status_code}")
                # 打印响应体以调试
                try:
                    print(f"响应内容: {response.text}")
                except:
                    pass
        except Exception as e:
            print(f"{log_prefix}第 {i}/{len(final_batches)} 批次发送出错 [{report_type}]：{e}")

    print(f"{log_prefix}所有 {len(final_batches)} 批次发送完成 [{report_type}]")
    return True


def send_to_email(
    from_email: str,
    password: str,
    to_email: str,
    report_type: str,
    html_file_path: str,
    custom_smtp_server: Optional[str] = None,
    custom_smtp_port: Optional[int] = None,
    *,
    get_time_func: Callable = None,
) -> bool:
    try:
        if not html_file_path or not Path(html_file_path).exists():
            return False

        with open(html_file_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        domain = from_email.split("@")[-1].lower()

        if custom_smtp_server and custom_smtp_port:
            smtp_server = custom_smtp_server
            smtp_port = int(custom_smtp_port)
            if smtp_port == 465:
                use_tls = False
            elif smtp_port == 587:
                use_tls = True
            else:
                use_tls = True
        elif domain in SMTP_CONFIGS:
            config = SMTP_CONFIGS[domain]
            smtp_server = config["server"]
            smtp_port = config["port"]
            use_tls = config["encryption"] == "TLS"
        else:
            smtp_server = f"smtp.{domain}"
            smtp_port = 587
            use_tls = True

        msg = MIMEMultipart("alternative")
        msg["From"] = formataddr(("TrendRadar", from_email))
        recipients = [addr.strip() for addr in to_email.split(",")]
        msg["To"] = ", ".join(recipients) if len(recipients) > 1 else recipients[0]

        now = get_time_func() if get_time_func else datetime.now()
        subject = f"TrendRadar 热点分析报告 - {report_type} - {now.strftime('%m月%d日 %H:%M')}"
        msg["Subject"] = Header(subject, "utf-8")
        msg["MIME-Version"] = "1.0"
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()

        text_content = f"TrendRadar 热点分析报告\n========================\n报告类型：{report_type}\n生成时间：{now.strftime('%Y-%m-%d %H:%M:%S')}\n\n请使用支持HTML的邮件客户端查看完整报告内容。"
        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        if use_tls:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)
        
        server.login(from_email, password)
        server.send_message(msg)
        server.quit()
        print(f"邮件发送成功 [{report_type}] -> {to_email}")
        return True

    except Exception as e:
        print(f"邮件发送失败 [{report_type}]：{e}")
        return False

def send_to_ntfy(
    server_url: str,
    topic: str,
    token: Optional[str],
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    account_label: str = "",
    *,
    batch_size: int = 3800,
    split_content_func: Callable = None,
    rss_items: Optional[list] = None,
    rss_new_items: Optional[list] = None,
    ai_analysis: Any = None,
    display_regions: Optional[Dict] = None,
    standalone_data: Optional[Dict] = None,
) -> bool:
    log_prefix = f"ntfy{account_label}" if account_label else "ntfy"
    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "Markdown": "yes",
        "Title": report_type,
        "Priority": "default",
        "Tags": "news",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    base_url = server_url.rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        base_url = f"https://{base_url}"
    url = f"{base_url}/{topic}"

    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    ai_content = None
    ai_stats = None
    if ai_analysis:
        ai_content = _render_ai_analysis(ai_analysis, "ntfy")
        if getattr(ai_analysis, "success", False):
            ai_stats = {
                "total_news": getattr(ai_analysis, "total_news", 0),
                "analyzed_news": getattr(ai_analysis, "analyzed_news", 0),
                "max_news_limit": getattr(ai_analysis, "max_news_limit", 0),
                "hotlist_count": getattr(ai_analysis, "hotlist_count", 0),
                "rss_count": getattr(ai_analysis, "rss_count", 0),
            }

    header_reserve = get_max_batch_header_size("ntfy")
    batches = split_content_func(
        report_data, "ntfy", update_info, max_bytes=batch_size - header_reserve, mode=mode,
        rss_items=rss_items,
        rss_new_items=rss_new_items,
        ai_content=ai_content,
        standalone_data=standalone_data,
        ai_stats=ai_stats,
        report_type=report_type,
    )
    batches = add_batch_headers(batches, "ntfy", batch_size)
    reversed_batches = list(reversed(batches))
    total_batches = len(batches)

    success_count = 0
    for idx, batch_content in enumerate(reversed_batches, 1):
        actual_batch_num = total_batches - idx + 1
        current_headers = headers.copy()
        if total_batches > 1:
            current_headers["Title"] = f"{report_type} ({actual_batch_num}/{total_batches})"

        try:
            response = requests.post(url, headers=current_headers, data=batch_content.encode("utf-8"), proxies=proxies, timeout=30)
            if response.status_code == 200:
                print(f"{log_prefix}第 {actual_batch_num}/{total_batches} 批次发送成功 [{report_type}]")
                success_count += 1
                time.sleep(1)
            else:
                print(f"{log_prefix}第 {actual_batch_num}/{total_batches} 批次发送失败 [{report_type}]，状态码：{response.status_code}")
        except Exception as e:
            print(f"{log_prefix}第 {actual_batch_num}/{total_batches} 批次发送异常 [{report_type}]：{e}")

    return success_count == total_batches

def send_to_bark(
    bark_url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    account_label: str = "",
    *,
    batch_size: int = 3600,
    batch_interval: float = 1.0,
    split_content_func: Callable = None,
    rss_items: Optional[list] = None,
    rss_new_items: Optional[list] = None,
    ai_analysis: Any = None,
    display_regions: Optional[Dict] = None,
    standalone_data: Optional[Dict] = None,
) -> bool:
    log_prefix = f"Bark{account_label}" if account_label else "Bark"
    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    parsed_url = urlparse(bark_url)
    device_key = parsed_url.path.strip('/').split('/')[0] if parsed_url.path else None
    api_endpoint = f"{parsed_url.scheme}://{parsed_url.netloc}/push"

    ai_content = None
    ai_stats = None
    if ai_analysis:
        ai_content = _render_ai_analysis(ai_analysis, "bark")
        if getattr(ai_analysis, "success", False):
            ai_stats = {
                "total_news": getattr(ai_analysis, "total_news", 0),
                "analyzed_news": getattr(ai_analysis, "analyzed_news", 0),
                "max_news_limit": getattr(ai_analysis, "max_news_limit", 0),
                "hotlist_count": getattr(ai_analysis, "hotlist_count", 0),
                "rss_count": getattr(ai_analysis, "rss_count", 0),
            }

    header_reserve = get_max_batch_header_size("bark")
    batches = split_content_func(
        report_data, "bark", update_info, max_bytes=batch_size - header_reserve, mode=mode,
        rss_items=rss_items,
        rss_new_items=rss_new_items,
        ai_content=ai_content,
        standalone_data=standalone_data,
        ai_stats=ai_stats,
        report_type=report_type,
    )
    batches = add_batch_headers(batches, "bark", batch_size)
    reversed_batches = list(reversed(batches))
    total_batches = len(batches)

    success_count = 0
    for idx, batch_content in enumerate(reversed_batches, 1):
        actual_batch_num = total_batches - idx + 1
        payload = {
            "title": report_type,
            "markdown": batch_content,
            "device_key": device_key,
            "group": "TrendRadar",
        }
        try:
            response = requests.post(api_endpoint, json=payload, proxies=proxies, timeout=30)
            if response.status_code == 200:
                print(f"{log_prefix}第 {actual_batch_num}/{total_batches} 批次发送成功 [{report_type}]")
                success_count += 1
                time.sleep(batch_interval)
            else:
                print(f"{log_prefix}第 {actual_batch_num}/{total_batches} 批次发送失败 [{report_type}]")
        except Exception as e:
            print(f"{log_prefix}第 {actual_batch_num}/{total_batches} 批次发送异常 [{report_type}]：{e}")

    return success_count == total_batches

def send_to_slack(
    webhook_url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    account_label: str = "",
    *,
    batch_size: int = 4000,
    batch_interval: float = 1.0,
    split_content_func: Callable = None,
    rss_items: Optional[list] = None,
    rss_new_items: Optional[list] = None,
    ai_analysis: Any = None,
    display_regions: Optional[Dict] = None,
    standalone_data: Optional[Dict] = None,
) -> bool:
    headers = {"Content-Type": "application/json"}
    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}
    log_prefix = f"Slack{account_label}" if account_label else "Slack"

    ai_content = None
    ai_stats = None
    if ai_analysis:
        ai_content = _render_ai_analysis(ai_analysis, "slack")
        if getattr(ai_analysis, "success", False):
            ai_stats = {
                "total_news": getattr(ai_analysis, "total_news", 0),
                "analyzed_news": getattr(ai_analysis, "analyzed_news", 0),
                "max_news_limit": getattr(ai_analysis, "max_news_limit", 0),
                "hotlist_count": getattr(ai_analysis, "hotlist_count", 0),
                "rss_count": getattr(ai_analysis, "rss_count", 0),
            }

    header_reserve = get_max_batch_header_size("slack")
    batches = split_content_func(
        report_data, "slack", update_info, max_bytes=batch_size - header_reserve, mode=mode,
        rss_items=rss_items,
        rss_new_items=rss_new_items,
        ai_content=ai_content,
        standalone_data=standalone_data,
        ai_stats=ai_stats,
        report_type=report_type,
    )
    batches = add_batch_headers(batches, "slack", batch_size)

    for i, batch_content in enumerate(batches, 1):
        mrkdwn_content = convert_markdown_to_mrkdwn(batch_content)
        payload = {"text": mrkdwn_content}
        try:
            response = requests.post(webhook_url, headers=headers, json=payload, proxies=proxies, timeout=30)
            if response.status_code == 200:
                print(f"{log_prefix}第 {i}/{len(batches)} 批次发送成功 [{report_type}]")
                time.sleep(batch_interval)
            else:
                print(f"{log_prefix}第 {i}/{len(batches)} 批次发送失败 [{report_type}]")
                return False
        except Exception as e:
            print(f"{log_prefix}第 {i}/{len(batches)} 批次发送出错 [{report_type}]：{e}")
            return False
    return True

def send_to_generic_webhook(
    webhook_url: str,
    payload_template: Optional[str],
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    account_label: str = "",
    *,
    batch_size: int = 4000,
    batch_interval: float = 1.0,
    split_content_func: Optional[Callable] = None,
    rss_items: Optional[list] = None,
    rss_new_items: Optional[list] = None,
    ai_analysis: Any = None,
    display_regions: Optional[Dict] = None,
    standalone_data: Optional[Dict] = None,
) -> bool:
    if split_content_func is None:
        raise ValueError("split_content_func is required")

    headers = {"Content-Type": "application/json"}
    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}
    log_prefix = f"通用Webhook{account_label}" if account_label else "通用Webhook"

    ai_content = None
    ai_stats = None
    if ai_analysis:
        ai_content = _render_ai_analysis(ai_analysis, "wework")
        if getattr(ai_analysis, "success", False):
            ai_stats = {
                "total_news": getattr(ai_analysis, "total_news", 0),
                "analyzed_news": getattr(ai_analysis, "analyzed_news", 0),
                "max_news_limit": getattr(ai_analysis, "max_news_limit", 0),
                "hotlist_count": getattr(ai_analysis, "hotlist_count", 0),
                "rss_count": getattr(ai_analysis, "rss_count", 0),
            }

    template_overhead = 200 
    batches = split_content_func(
        report_data, "wework", update_info, max_bytes=batch_size - template_overhead, mode=mode,
        rss_items=rss_items,
        rss_new_items=rss_new_items,
        ai_content=ai_content,
        standalone_data=standalone_data,
        ai_stats=ai_stats,
        report_type=report_type,
    )
    batches = add_batch_headers(batches, "wework", batch_size)

    for i, batch_content in enumerate(batches, 1):
        try:
            if payload_template:
                json_content = json.dumps(batch_content)[1:-1]
                json_title = json.dumps(report_type)[1:-1]
                payload_str = payload_template.replace("{content}", json_content).replace("{title}", json_title)
                try:
                    payload = json.loads(payload_str)
                except json.JSONDecodeError:
                    payload = {"title": report_type, "content": batch_content}
            else:
                payload = {"title": report_type, "content": batch_content}

            response = requests.post(webhook_url, headers=headers, json=payload, proxies=proxies, timeout=30)
            if 200 <= response.status_code < 300:
                print(f"{log_prefix}第 {i}/{len(batches)} 批次发送成功 [{report_type}]")
                time.sleep(batch_interval)
            else:
                print(f"{log_prefix}第 {i}/{len(batches)} 批次发送失败 [{report_type}]，状态码：{response.status_code}")
                return False
        except Exception as e:
            print(f"{log_prefix}第 {i}/{len(batches)} 批次发送出错 [{report_type}]：{e}")
            return False
    return True
