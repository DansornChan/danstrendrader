# coding=utf-8
"""
通知内容渲染模块（Renderer）

职责：
- 将分析结果渲染为结构化文本块
- 控制“展示逻辑”，不控制发送、不控制字数
"""

from datetime import datetime
from typing import Dict, Any, List
from collections import defaultdict

# ✅ 引入重要性评分
from trendradar.ai.analyzer import calc_importance_score


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
    def render(self, input_data: Dict[str, Any]) -> Dict[str, str]:
        report_data = input_data.get("report_data", {}) if isinstance(input_data, dict) else input_data
        ai_analysis = input_data.get("ai_analysis")
        portfolio = input_data.get("portfolio")
        history_summary = input_data.get("history_summary")
        rss_items = input_data.get("rss_items", [])
        standalone_data = input_data.get("standalone_data")

        hot_topics = self._render_hot_topics(report_data)
        rss_block = self._render_rss_items(rss_items)
        standalone_block = self._render_standalone_data(standalone_data)
        ai_block = self._render_ai_analysis(ai_analysis)
        portfolio_block = self._render_portfolio_impact(portfolio, report_data)
        trend_block = self._render_trend_compare(history_summary, ai_analysis)

        full_text = "\n\n".join(
            b for b in [
                hot_topics,
                rss_block,
                standalone_block,
                ai_block,
                portfolio_block,
                trend_block
            ] if b and b.strip()
        )

        return {
            "hot_topics": hot_topics,
            "rss_items": rss_block,
            "standalone_data": standalone_block,
            "ai_analysis": ai_block,
            "portfolio_impact": portfolio_block,
            "trend_compare": trend_block,
            "full_text": full_text,
        }

    # =========================
    # ① 分领域重点新闻（核心升级点）
    # =========================
    def _render_hot_topics(self, report_data: Dict[str, Any]) -> str:
        stats = report_data.get("stats", [])
        if not stats:
            return ""

        lines = [
            "🔥 **分领域重点新闻**",
            f"时间：{self.now.strftime('%Y-%m-%d %H:%M')}",
            ""
        ]

        total_count = 0

        for stat in stats:
            word = stat.get("word", "未分类")
            titles = stat.get("titles", [])
            if not titles:
                continue

            # === 核心：给每条新闻打分 ===
            scored_items = []
            for item in titles:
                if not isinstance(item, dict):
                    continue
                text = item.get("title") or item.get("content", "")
                score = calc_importance_score(
                    text=text,
                    hit_words=item.get("hit_words"),
                    is_signal=item.get("is_signal", False)
                )
                scored_items.append((score, item))

            # 按重要性排序
            scored_items.sort(key=lambda x: x[0], reverse=True)

            # 每个板块展示 3–5 条（不死卡）
            display_items = scored_items[:5]
            if len(display_items) < 3:
                display_items = scored_items[:3]

            lines.append(f"【{word}】（{len(display_items)}条）")

            for _, item in display_items:
                title = item.get("title", "无标题")
                url = item.get("url") or item.get("mobile_url", "")
                source = item.get("source_name", "")
                time_display = item.get("time_display", "")

                clean_title = title.replace("[", "【").replace("]", "】").replace("(", "（").replace(")", "）")
                if len(clean_title) > 70:
                    clean_title = clean_title[:67] + "..."

                if url.startswith("http"):
                    title_display = f"[{clean_title}]({url})"
                else:
                    title_display = clean_title

                meta = " | ".join(p for p in [source, time_display] if p)
                meta_str = f"（{meta}）" if meta else ""

                lines.append(f"  - {title_display}{meta_str}")

            lines.append("")
            total_count += len(display_items)

        if total_count == 0:
            return ""

        lines.insert(2, f"总计：{total_count}条重点新闻")
        return "\n".join(lines).strip()

    # =========================
    # ② RSS（保持原逻辑，略微放宽）
    # =========================
    def _render_rss_items(self, rss_items: List[Dict]) -> str:
        if not rss_items:
            return ""

        lines = ["📰 **RSS 深度新闻**", ""]
        for rss_stat in rss_items:
            word = rss_stat.get("word", "未分类")
            titles = rss_stat.get("titles", [])
            if not titles:
                continue

            lines.append(f"【{word}】")
            for item in titles[:5]:
                title = item.get("title", "")
                url = item.get("url", "")
                if not title:
                    continue

                if len(title) > 80:
                    title = title[:77] + "..."

                if url.startswith("http"):
                    lines.append(f"  - [{title}]({url})")
                else:
                    lines.append(f"  - {title}")

            lines.append("")

        return "\n".join(lines).strip()

    # =========================
    # ③ 独立展示区（不动）
    # =========================
    def _render_standalone_data(self, standalone_data: Dict[str, Any]) -> str:
        if not standalone_data:
            return ""
        return ""

    # =========================
    # ④ AI 综合研判（只做“清洗 + 保完整”）
    # =========================
    def _render_ai_analysis(self, ai_analysis: Any) -> str:
        if not ai_analysis or not getattr(ai_analysis, "success", False):
            return ""

        lines = ["🧠 **AI 综合研判**", ""]

        for title, field in [
            ("核心热点态势", "core_trends"),
            ("舆论风向争议", "sentiment_controversy"),
            ("异动与弱信号", "signals"),
            ("RSS 深度洞察", "rss_insights"),
        ]:
            content = getattr(ai_analysis, field, "")
            if content:
                lines.append(f"**{title}**")
                lines.append("")
                lines.append(content.strip())
                lines.append("")

        if getattr(ai_analysis, "outlook_strategy", ""):
            lines.append("💡 **研判策略建议**")
            lines.append("")
            lines.append(ai_analysis.outlook_strategy.strip())
            lines.append("")

        if getattr(ai_analysis, "policy_deep_dive", ""):
            lines.append("🏛️ **重大政策全文解读**")
            lines.append("")
            lines.append(ai_analysis.policy_deep_dive.strip())

        return "\n".join(lines).strip()

    # =========================
    # ⑤ 持仓影响（保留）
    # =========================
    def _render_portfolio_impact(self, portfolio, report_data) -> str:
        if not portfolio:
            return ""
        lines = ["📊 **持仓相关影响分析**", ""]
        for stock in portfolio:
            lines.append(f"- {stock.get('name')}（{stock.get('code')}）")
        return "\n".join(lines)

    # =========================
    # ⑥ 趋势对比（保留）
    # =========================
    def _render_trend_compare(self, history_summary, ai_analysis) -> str:
        if not history_summary:
            return ""

        sectors = history_summary.get("sectors", {})
        if not sectors:
            return ""

        report_date = history_summary.get("date", self.now.strftime("%Y-%m-%d"))
        lines = [
            "📊 Danstrendradar 每日投资雷达",
            f"📅 {report_date}",
            "",
            "🌀 板块强度排名（含动量）",
            "",
        ]

        ordered = sorted(sectors.items(), key=lambda x: x[1].get("rank", 999))
        rank_marks = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]

        for idx, (name, data) in enumerate(ordered):
            strength = float(data.get("strength", 0))
            momentum = data.get("momentum", "N/A")
            rank_change = data.get("rank_change", None)

            strength_arrow = "🔼" if strength > 0 else ("🔽" if strength < 0 else "→")

            if momentum == "N/A":
                momentum_text = "N/A"
                momentum_arrow = "→"
            else:
                momentum_val = float(momentum)
                momentum_text = f"{momentum_val:+.1f}"
                momentum_arrow = "↑" if momentum_val > 0 else ("↓" if momentum_val < 0 else "→")

            if rank_change is None:
                rank_change_text = "新"
            elif rank_change > 0:
                rank_change_text = f"+{rank_change} 位"
            elif rank_change < 0:
                rank_change_text = f"{rank_change} 位"
            else:
                rank_change_text = "→"

            rank_mark = rank_marks[idx] if idx < len(rank_marks) else f"{idx + 1}."
            lines.append(f"{rank_mark} {name}：{strength:+.1f} {strength_arrow}")
            lines.append(f"   动量：{momentum_text} {momentum_arrow}")
            lines.append(f"   排名变化：{rank_change_text}")
            lines.append("")

        strongest_sector = ordered[0][0] if ordered else "暂无"
        momentum_candidates = [
            (n, d.get("momentum")) for n, d in ordered if d.get("momentum") != "N/A"
        ]
        momentum_candidates = [(n, float(m)) for n, m in momentum_candidates]

        if momentum_candidates:
            top_momentum_sector, top_momentum = max(momentum_candidates, key=lambda x: x[1])
            negative_momentum = [n for n, m in momentum_candidates if m < 0]
            neg_text = "、".join(negative_momentum[:3]) if negative_momentum else "暂无"
            risk_text = "整体市场风险偏中性。" if len(negative_momentum) <= len(momentum_candidates) / 2 else "整体市场风险偏谨慎。"
            momentum_sentence = f"{top_momentum_sector}板块动量最强（{top_momentum:+.1f}），存在短线强化迹象。"
        else:
            neg_text = "暂无"
            risk_text = "整体市场风险偏中性。"
            momentum_sentence = "暂无可比昨日数据的动量信息。"

        lines.extend([
            "⚡ 趋势判断",
            f"当前最强板块：{strongest_sector}。",
            f"当前动量最大板块：{momentum_sentence}",
            f"当前动量转负板块：{neg_text}。",
            risk_text,
        ])

        return "\n".join(lines).strip()
