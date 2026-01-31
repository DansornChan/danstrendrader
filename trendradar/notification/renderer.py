# coding=utf-8
"""
通知内容渲染模块（Renderer）

职责：
- 将分析结果渲染为"结构化文本块"
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
    def render(self, input_data: Dict[str, Any]) -> Dict[str, str]:
        if isinstance(input_data, dict) and "report_data" in input_data:
            report_data = input_data.get("report_data", {})
            ai_analysis = input_data.get("ai_analysis")
            portfolio = input_data.get("portfolio")
            history_summary = input_data.get("history_summary")
            rss_items = input_data.get("rss_items", [])
            standalone_data = input_data.get("standalone_data")
        else:
            report_data = input_data
            ai_analysis = None
            portfolio = None
            history_summary = None
            rss_items = []
            standalone_data = None

        # 渲染各个模块
        hot_topics = self._render_hot_topics(report_data)
        rss_block = self._render_rss_items(rss_items)
        standalone_block = self._render_standalone_data(standalone_data)
        ai_block = self._render_ai_analysis(ai_analysis)
        portfolio_block = self._render_portfolio_impact(portfolio, report_data)
        trend_block = self._render_trend_compare(history_summary, ai_analysis)

        # 拼装完整文本
        full_text = "\n\n".join(
            block for block in [
                hot_topics,
                rss_block,
                standalone_block,
                ai_block,
                portfolio_block,
                trend_block
            ] if block and block.strip()
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
    # ① 分领域重点新闻
    # =========================
    def _render_hot_topics(self, report_data: Dict[str, Any]) -> str:
        if not report_data:
            return ""

        if 'stats' not in report_data or not isinstance(report_data['stats'], list):
            return ""

        stats = report_data['stats']
        if not stats:
            return ""

        lines = [
            f"🔥 **分领域重点新闻**",
            f"时间：{self.now.strftime('%Y-%m-%d %H:%M')}",
            ""
        ]

        total_display_count = 0
        
        for stat in stats:
            word = stat.get('word', '未命名')
            count = stat.get('count', 0)
            titles = stat.get('titles', [])
            
            if not titles:
                continue
                
            display_count = len(titles)
            total_display_count += display_count
            
            if count != display_count:
                lines.append(f"【{word}】（{display_count}条/原始{count}条）")
            else:
                lines.append(f"【{word}】（{display_count}条）")
            
            for title_item in titles:
                if isinstance(title_item, dict):
                    title = title_item.get('title') or title_item.get('content') or "无标题"
                    source = title_item.get('source_name', '')
                    time_display = title_item.get('time_display', '')
                    ranks = title_item.get('ranks', [])
                    is_new = title_item.get('is_new', False)
                    
                    if len(title) > 60:
                        title_display = title[:57] + "..."
                    else:
                        title_display = title
                    
                    display_parts = []
                    if source:
                        display_parts.append(f"{source}")
                    if time_display:
                        display_parts.append(f"{time_display}")
                    
                    if ranks:
                        last_rank = ranks[-1] if isinstance(ranks, list) and ranks else ranks
                        display_parts.append(f"第{last_rank}位")
                    
                    if is_new:
                        display_parts.append("🆕")
                    
                    if display_parts:
                        info_str = "（" + " | ".join(display_parts) + "）"
                    else:
                        info_str = ""
                    
                    lines.append(f"  - {title_display}{info_str}")
                else:
                    title_str = str(title_item)
                    if len(title_str) > 60:
                        title_str = title_str[:57] + "..."
                    lines.append(f"  - {title_str}")
            
            lines.append("")

        if total_display_count == 0:
            return ""
            
        lines.insert(2, f"总计：{total_display_count}条重点新闻")
        
        return "\n".join(lines).strip()

    # =========================
    # ② RSS 项目渲染
    # =========================
    def _render_rss_items(self, rss_items: List[Dict]) -> str:
        if not rss_items:
            return ""

        lines = ["📰 **RSS 深度新闻**", ""]

        total_display_count = 0
        
        for rss_stat in rss_items:
            word = rss_stat.get('word', '未分类')
            count = rss_stat.get('count', 0)
            titles = rss_stat.get('titles', [])
            
            if not titles:
                continue
                
            display_count = len(titles)
            total_display_count += display_count
            
            lines.append(f"【{word}】（{display_count}条）")
            
            for title_item in titles:
                if isinstance(title_item, dict):
                    title = title_item.get('title', '无标题')
                    feed_name = title_item.get('feed_name', '')
                    published_at = title_item.get('published_at', '')
                    
                    if len(title) > 60:
                        title = title[:57] + "..."
                    
                    info_parts = []
                    if feed_name:
                        info_parts.append(feed_name)
                    if published_at:
                        info_parts.append(published_at)
                    
                    if info_parts:
                        info_str = "（" + " | ".join(info_parts) + "）"
                    else:
                        info_str = ""
                    
                    lines.append(f"  - {title}{info_str}")
                else:
                    lines.append(f"  - {str(title_item)}")
            
            lines.append("")
            
        if total_display_count == 0:
            return ""
            
        lines.insert(1, f"总计：{total_display_count}条RSS新闻")
        
        return "\n".join(lines).strip()

    # =========================
    # ③ 独立展示区渲染
    # =========================
    def _render_standalone_data(self, standalone_data: Dict[str, Any]) -> str:
        if not standalone_data:
            return ""

        lines = ["🏆 **独立展示区**", ""]

        if 'platforms' in standalone_data and standalone_data['platforms']:
            lines.append("🔥 热门平台榜单：")
            for platform in standalone_data['platforms']:
                platform_name = platform.get('name', '未知平台')
                items = platform.get('items', [])
                
                if items:
                    lines.append(f"\n【{platform_name}】")
                    for item in items[:5]:
                        title = item.get('title', '')
                        rank = item.get('rank', '')
                        if title and rank:
                            if len(title) > 50:
                                title = title[:47] + "..."
                            lines.append(f"  {rank}. {title}")
            lines.append("")

        if 'rss_feeds' in standalone_data and standalone_data['rss_feeds']:
            lines.append("📰 精选RSS源：")
            for rss_feed in standalone_data['rss_feeds']:
                feed_name = rss_feed.get('name', '未知源')
                items = rss_feed.get('items', [])
                
                if items:
                    lines.append(f"\n【{feed_name}】")
                    for item in items[:3]:
                        title = item.get('title', '')
                        published_at = item.get('published_at', '')
                        if title:
                            if len(title) > 60:
                                title = title[:57] + "..."
                            if published_at:
                                lines.append(f"  - {title}（{published_at}）")
                            else:
                                lines.append(f"  - {title}")
            lines.append("")

        return "\n".join(lines).strip()

    # =========================
    # ④ AI 研判（修复重复标题问题）
    # =========================
    def _render_ai_analysis(self, ai_analysis: Any) -> str:
        if not ai_analysis or not getattr(ai_analysis, "success", False):
            return ""

        lines = []
        
        # 获取 core_trends
        core_trends = getattr(ai_analysis, "core_trends", "")
        if not core_trends:
            return ""
        
        # 清理core_trends中可能已有的标题
        cleaned_core_trends = core_trends.strip()
        
        # 移除常见的AI标题前缀
        title_prefixes = [
            "🤖 AI 综合研判",
            "🧠 AI 综合研判", 
            "AI 综合研判",
            "【AI分析】",
            "【AI研判】",
            "热度定性：",
            "整体热度："
        ]
        
        for prefix in title_prefixes:
            if cleaned_core_trends.startswith(prefix):
                cleaned_core_trends = cleaned_core_trends[len(prefix):].strip()
                if cleaned_core_trends.startswith("："):
                    cleaned_core_trends = cleaned_core_trends[1:].strip()
        
        # 添加AI标题（只在renderer中添加一次）
        lines.extend([
            "🧠 **AI 综合研判**",
            "",
            cleaned_core_trends,
            ""
        ])

        # 产业分析
        if getattr(ai_analysis, "industry_analysis", None):
            lines.append("📊 **产业分析**")
            for industry in ai_analysis.industry_analysis:
                category = industry.get('category', '未分类')
                summary = industry.get('summary', '')
                sentiment = industry.get('sentiment', 'Neutral')
                
                sentiment_emoji = {
                    'Positive': '📈',
                    'Negative': '📉',
                    'Neutral': '➡️'
                }.get(sentiment, '➡️')
                
                if len(summary) > 100:
                    summary = summary[:97] + "..."
                    
                lines.append(f"{sentiment_emoji}【{category}】{summary}")
            lines.append("")

        # 结论判断
        conclusion = getattr(ai_analysis, "conclusion", "")
        if conclusion:
            lines.extend([
                "📌 **结论判断**",
                conclusion.strip(),
                ""
            ])

        return "\n".join(lines).strip()

    # =========================
    # ⑤ 持仓影响分析
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
            name = stock.get("name", "未知")
            code = stock.get("code", "")
            sector = stock.get("sector", "")

            lines.append(f"🔹 **{name}（{code}）**")
            
            if 'stats' in report_data and isinstance(report_data['stats'], list):
                for stat in report_data['stats']:
                    word = stat.get('word', '')
                    if sector and sector.lower() in word.lower():
                        titles = stat.get('titles', [])
                        for i, title_item in enumerate(titles[:2]):
                            if isinstance(title_item, dict):
                                title = title_item.get('title', '相关动态')
                                if len(title) > 40:
                                    title = title[:37] + "..."
                                lines.append(f"  - {title}")
            
            lines.append("")

        return "\n".join(lines).strip()

    # =========================
    # ⑥ 历史趋势对比
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