# coding=utf-8
"""
通知内容格式转换模块

提供不同推送平台间的格式转换功能
"""

import re
from typing import Dict, List


# ----------------------------------------------------------------------
# 原有函数（完全保留）
# ----------------------------------------------------------------------

def strip_markdown(text: str) -> str:
    """去除文本中的 markdown 语法格式，用于个人微信推送"""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 \2', text)
    text = re.sub(r'!\[(.+?)\]\(.+?\)', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\-\*]{3,}\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'<font[^>]*>(.+?)</font>', r'\1', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def convert_markdown_to_mrkdwn(content: str) -> str:
    """将标准 Markdown 转换为 Slack 的 mrkdwn 格式"""
    content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<\2|\1>', content)
    content = re.sub(r'\*\*([^*]+)\*\*', r'*\1*', content)
    return content


# ----------------------------------------------------------------------
# ⭐ 新增：AI 分析结构解析（核心）
# ----------------------------------------------------------------------

SECTION_PATTERNS = {
    "macro": r"【宏观主线】",
    "industry": r"【产业主线】",
    "signals": r"\*\*异动与弱信号\*\*",
    "rss": r"\*\*RSS 深度洞察\*\*",
    "strategy": r"\*\*研判策略建议\*\*",
}


def parse_ai_analysis_sections(text: str) -> Dict[str, str]:
    """
    将 AI 输出的完整分析文本解析为结构化区块

    Returns:
        {
            "full": 原始全文,
            "macro": "...",
            "industry": "...",
            "signals": "...",
            "rss": "...",
            "strategy": "...",
            "portfolio_refs": [...]
        }
    """
    sections: Dict[str, str] = {"full": text}

    # 先统一文本，避免解析受 markdown 干扰
    raw = text.strip()

    # 找到所有锚点的位置
    anchors: List[tuple] = []
    for key, pattern in SECTION_PATTERNS.items():
        match = re.search(pattern, raw)
        if match:
            anchors.append((key, match.start()))

    # 按出现顺序排序
    anchors.sort(key=lambda x: x[1])

    # 切片提取内容
    for idx, (key, start) in enumerate(anchors):
        end = anchors[idx + 1][1] if idx + 1 < len(anchors) else len(raw)
        sections[key] = raw[start:end].strip()

    # ------------------------------------------------------------------
    # 提取【🔴 持仓关联】相关内容
    # ------------------------------------------------------------------
    portfolio_refs = []
    for match in re.finditer(r"【🔴 持仓关联】(.+?)(?=\n\n|\n【|$)", raw, re.S):
        content = match.group(1).strip()
        portfolio_refs.append(content)

    sections["portfolio_refs"] = portfolio_refs

    return sections