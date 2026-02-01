# coding=utf-8
from datetime import datetime

STRONG_KEYWORDS = [
    "突破", "减产", "制裁", "ETF", "资金流入",
    "爆仓", "加息", "降息", "禁令"
]

STRONG_CATEGORIES = [
    "原油", "能源", "比特币", "加密货币",
    "铜", "航运", "美联储", "地缘"
]


def classify_signal(title: str, category: str, weight: int) -> str:
    score = 0

    if weight >= 5:
        score += 1

    if any(k in title for k in STRONG_KEYWORDS):
        score += 1

    if any(c in category for c in STRONG_CATEGORIES):
        score += 1

    if score >= 2:
        return "STRONG"
    elif weight >= 3:
        return "MID"
    else:
        return "WEAK"


def format_signal_for_telegram(signal: dict) -> str:
    """
    signal = {
        "title": str,
        "summary": str,
        "category": str,
        "weight": int,
        "source": str,
        "url": str
    }
    """

    level = classify_signal(
        signal.get("title", ""),
        signal.get("category", ""),
        signal.get("weight", 0)
    )

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    header = {
        "STRONG": "🚨【强信号】",
        "MID": "⚠️【中信号】",
        "WEAK": "ℹ️【快讯】"
    }[level]

    return f"""
{header}
━━━━━━━━━━━━━━
📌 标题：{signal.get('title', '')}
🏷 分类：{signal.get('category', '')}
⭐ 权重：{signal.get('weight', 0)}
🕒 时间：{now}

{signal.get('summary', '')}

🔗 {signal.get('url', '')}
""".strip()