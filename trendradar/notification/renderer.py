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
        # ✅ 修复点：补全了 datetime.now()
        self.now = get_time_func() if get_time_func else datetime.now()

    # =========================
    # 对外唯一入口（已修复参数接收问题）
    # =========================
    def render(self, input_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Input:
            input_data: 也就是 Dispatcher 传进来的 analysis_result
                        它可能直接是新闻数据，也可能是一个包含所有信息的字典。
        """
        
        # 1. 尝试解包数据 (假设 input_data 是一个包含所有信息的“大字典”)
        # 如果 input_data 里有 "report_data" 这个 key，说明它是封装好的
        if isinstance(input_data, dict) and "report_data" in input_data:
            report_data = input_data.get("report_data", {})
            ai_analysis = input_data.get("ai_analysis")
            portfolio = input_data.get("portfolio")
            history_summary = input_data.get("history_summary")
        else:
            # 2. 兼容模式 (假设 input_data 本身就是 report_data)
            # 这种情况会导致 AI 分析等内容无法显示，但至少新闻能出来
            report_data = input_data
            ai_analysis = None
            portfolio = None
            history_summary = None

        # 3. 开始渲染各个模块
        hot_topics = self._render_hot_topics(report_data)
        ai_block = self._render_ai_analysis(ai_analysis)
        portfolio_block = self._render_portfolio_impact(portfolio, report_data)
        trend_block = self._render_trend_compare(history_summary, ai_analysis)

        # 4. 拼装完整文本
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
    # ① 分领域重点新闻（已修复标题获取问题）
    # =========================
    def _render_hot_topics(self, report_data: Dict[str, Any]) -> str:
        if not report_data:
            return "⚠️ 无热点数据"

        lines = [
            f"🔥 **分领域重点新闻**",
            f"时间：{self.now.strftime('%Y-%m-%d %H:%M')}",
            ""
        ]

        # 🛡️ 防御性编程：只处理值为 list 的项，防止处理元数据字段
        if isinstance(report_data, dict):
            valid_sectors = {k: v for k, v in report_data.items() if isinstance(v, list)}
        else:
            return "⚠️ 数据格式错误"

        for sector, items in valid_sectors.items():
            if not items:
                continue

            lines.append(f"【{sector}】")
            freq_map = {}

            for item in items:
                # ✅ 修复点：增加多种键名尝试，防止取不到标题
                title = (
                    item.get("title") or 
                    item.get("content") or 
                    item.get("text") or 
                    item.get("url") or 
                    "未知标题"
                )
                
                # 截断过长的标题，防止刷屏
                if len(str(title)) > 50:
                    title = str(title)[:50] + "..."
                
                freq_map[title] = freq_map.get(title, 0) + 1

            # 按频率降序排列
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
            getattr(ai_analysis, "summary", "").strip(),
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
        if not portfolio or not report_data:
            return ""

        lines = ["📊 **持仓相关影响分析**", ""]

        for stock in portfolio:
            name = stock.get("name")
            code = stock.get("code")
            sector = stock.get("sector")

            # 尝试在 report_data 中找到对应板块的新闻
            related_news = report_data.get(sector, [])

            if not related_news:
                continue

            lines.append(f"🔹 **{name}（{code}）**")
            # 只取前3条相关新闻
            for news in related_news[:3]:
                news_title = news.get('title') or news.get('content') or "相关动态"
                impact = news.get("impact", "中性")
                lines.append(f"- {news_title} ｜ 影响：{impact}")

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
        
        if prev_trend:
            lines.append(f"昨日/上期判断：{prev_trend}")

        if ai_analysis and getattr(ai_analysis, "conclusion", None):
            lines.append(f"本次判断：{ai_analysis.conclusion}")

        if prev_trend and ai_analysis:
            if prev_trend == getattr(ai_analysis, "conclusion", ""):
                lines.append("➡️ 趋势判断延续")
            else:
                lines.append("⚠️ 趋势判断发生变化，需重点关注")

        return "\n".join(lines).strip()
