# coding=utf-8
"""
通知内容渲染模块（Renderer）

职责：
- 将分析结果渲染为“结构化文本块”
- 不关心发送平台、不关心字数限制
"""

from datetime import datetime
from typing import Dict, Any, List


class NotificationRenderer:
    def __init__(
        self,
        report_type: str,
        mode: str = "daily",
        account_label: str = "",
        get_time_func=None,
    ):
        self.report_type = report_type
        self.mode = mode
        self.account_label = account_label
        self.now = get_time_func() if get_time_func else datetime.now()

    # =========================
    # 对外唯一入口
    # =========================
    def render(
        self,
        report_data: Dict[str, Any],
        ai_analysis: Any = None,
        portfolio: List[Dict] = None,
        history_summary: Dict[str, Any] = None,
    ) -> Dict[str, str]:
        """
        返回结构化文本块，供 splitter 使用
        """

        hot_topics = self._render_hot_topics(report_data)
        ai_block = self._render_ai_analysis(ai_analysis)
        portfolio_block = self._render_portfolio_impact(portfolio, report_data)
        trend_block = self._render_trend_compare(history_summary, ai_analysis)

        full_text = "\n\n".join(
            block for block in [
                hot_topics,
                ai_block,
                portfolio_block,
                trend_block
            ] if block
        )

        return {
            "hot_topics": hot_topics,
            "ai_analysis": ai_block,
            "portfolio_impact": portfolio_block,
            "trend_compare": trend_block,
            "full_text": full_text,
        }

    # =========================
    # ① 分领域重点新闻
    # =========================
    def _render_hot_topics(self, report_data: Dict[str, Any]) -> str:
        if not report_data:
            return ""

        lines = [
            f"🔥 **分领域重点新闻**",
            f"时间：{self.now.strftime('%Y-%m-%d %H:%M')}",
            ""
        ]

        for sector, items in report_data.items():
            if not items:
                continue

            lines.append(f"【{sector}】")
            freq_map = {}

            for item in items:
                title = item.get("title", "")
                freq_map[title] = freq_map.get(title, 0) + 1

            for title, freq in sorted(freq_map.items(), key=lambda x: -x[1]):
                suffix = f"（出现 {freq} 次）" if freq > 1 else ""
                lines.append(f"- {title}{suffix}")

            lines.append("")

        return "\n".join(lines).strip()

    # =========================
    # ② AI 研判
    # =========================
    def _render_ai_analysis(self, ai_analysis: Any) -> str:
        if not ai_analysis or not getattr(ai_analysis, "success", False):
            return ""

        lines = [
            "🧠 **AI 综合研判**",
            "",
            ai_analysis.summary.strip(),
        ]

        if getattr(ai_analysis, "conclusion", None):
            lines.extend([
                "",
                "📌 **结论判断**",
                ai_analysis.conclusion.strip()
            ])

        return "\n".join(lines).strip()

    # =========================
    # ③ 持仓影响分析
    # =========================
    def _render_portfolio_impact(
        self,
        portfolio: List[Dict],
        report_data: Dict[str, Any],
    ) -> str:
        if not portfolio:
            return ""

        lines = ["📊 **持仓相关影响分析**", ""]

        for stock in portfolio:
            name = stock.get("name")
            code = stock.get("code")
            sector = stock.get("sector")

            related_news = report_data.get(sector, [])

            if not related_news:
                continue

            lines.append(f"🔹 **{name}（{code}）**")
            for news in related_news[:3]:
                impact = news.get("impact", "中性")
                lines.append(f"- {news.get('title')} ｜ 影响：{impact}")

            lines.append("")

        return "\n".join(lines).strip()

    # =========================
    # ④ 历史趋势对比
    # =========================
    def _render_trend_compare(
        self,
        history_summary: Dict[str, Any],
        ai_analysis: Any,
    ) -> str:
        if not history_summary:
            return ""

        lines = ["📈 **趋势对比分析（新 vs 历史）**", ""]

        prev_trend = history_summary.get("trend")
        prev_conclusion = history_summary.get("conclusion")

        if prev_trend:
            lines.append(f"昨日/上期判断：{prev_trend}")

        if ai_analysis and getattr(ai_analysis, "conclusion", None):
            lines.append(f"本次判断：{ai_analysis.conclusion}")

        if prev_trend and ai_analysis:
            if prev_trend == ai_analysis.conclusion:
                lines.append("➡️ 趋势判断延续")
            else:
                lines.append("⚠️ 趋势判断发生变化，需重点关注")

        return "\n".join(lines).strip()