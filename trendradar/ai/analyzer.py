# coding=utf-8
"""
AI 分析器模块

调用 AI 大模型对热点新闻进行深度分析
基于 LiteLLM 统一接口，支持 100+ AI 提供商
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from trendradar.ai.client import AIClient


@dataclass
class AIAnalysisResult:
    """AI 分析结果"""
    # 新版 5 核心板块
    core_trends: str = ""                # 核心热点与舆情态势
    sentiment_controversy: str = ""      # 舆论风向与争议
    signals: str = ""                    # 异动与弱信号
    rss_insights: str = ""               # RSS 深度洞察
    outlook_strategy: str = ""           # 研判与策略建议
    
    # === 【新增】股票分析专用数据 ===
    stock_analysis_data: List[Dict] = field(default_factory=list)

    # 基础元数据
    raw_response: str = ""               # 原始响应
    success: bool = False                # 是否成功
    error: str = ""                      # 错误信息

    # 新闻数量统计
    total_news: int = 0                  # 总新闻数（热榜+RSS）
    analyzed_news: int = 0               # 实际分析的新闻数
    max_news_limit: int = 0              # 分析上限配置值
    hotlist_count: int = 0               # 热榜新闻数
    rss_count: int = 0                   # RSS 新闻数


class AIAnalyzer:
    """AI 分析器"""

    def __init__(
        self,
        ai_config: Dict[str, Any],
        analysis_config: Dict[str, Any],
        get_time_func: Callable,
        debug: bool = False,
    ):
        """
        初始化 AI 分析器
        """
        self.ai_config = ai_config
        self.analysis_config = analysis_config
        self.get_time_func = get_time_func
        self.debug = debug

        # 创建 AI 客户端（基于 LiteLLM）
        self.client = AIClient(ai_config)

        # 验证配置
        try:
            result = self.client.validate_config()
        except Exception as e:
            logger.exception("[AI] validate_config 异常")
            result = (False, str(e))

        # 🔒 强制兜底，防止 None
        if not isinstance(result, tuple) or len(result) != 2:
            logger.error("[AI] validate_config 返回非法值，已兜底")
            valid, error = False, "AI 配置校验失败（返回值非法）"
        else:
            valid, error = result

        if not valid:
            raise RuntimeError(error)

        # 从分析配置获取功能参数
        self.max_news = analysis_config.get("MAX_NEWS_FOR_ANALYSIS", 50)
        self.include_rss = analysis_config.get("INCLUDE_RSS", True)
        self.include_rank_timeline = analysis_config.get("INCLUDE_RANK_TIMELINE", False)
        self.language = analysis_config.get("LANGUAGE", "Chinese")

        # 加载提示词模板
        self.system_prompt, self.user_prompt_template = self._load_prompt_template(
            analysis_config.get("PROMPT_FILE", "ai_analysis_prompt.txt")
        )

    def _load_prompt_template(self, prompt_file: str) -> tuple:
        """加载提示词模板"""
        try:
            current_dir = Path(__file__).parent
            # 向上找 config 目录
            config_dir = None
            for parent in [current_dir.parent, current_dir.parent.parent]:
                if (parent / "config").exists():
                    config_dir = parent / "config"
                    break
            
            if not config_dir:
                config_dir = Path(__file__).parent.parent.parent / "config"

            prompt_path = config_dir / prompt_file

            if not prompt_path.exists():
                print(f"[AI] 提示词文件不存在: {prompt_path}，将使用内置默认模板")
                return "你是一个金融分析师。", "{news_content}"

            content = prompt_path.read_text(encoding="utf-8")

            system_prompt = ""
            user_prompt = ""

            if "[system]" in content and "[user]" in content:
                parts = content.split("[user]")
                system_part = parts[0]
                user_part = parts[1] if len(parts) > 1 else ""

                if "[system]" in system_part:
                    system_prompt = system_part.split("[system]")[1].strip()
                user_prompt = user_part.strip()
            else:
                user_prompt = content

            return system_prompt, user_prompt
        except Exception as e:
            print(f"[AI] 加载模板出错: {e}")
            return "", "{news_content}"

    def analyze(
        self,
        stats: List[Dict],
        rss_stats: Optional[List[Dict]] = None,
        report_mode: str = "daily",
        report_type: str = "当日汇总",
        platforms: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        portfolio_context: str = "" 
    ) -> AIAnalysisResult:
        """
        执行 AI 分析
        """
        valid, error = self.client.validate_config()
        if not valid:
           return AIAnalysisResult(
               success=False,
               error=error
           )

        # 准备新闻内容并获取统计数据
        # 🟢 修复点：确保 _prepare_news_content 是 self 的方法，且已被定义
        news_content, rss_content, hotlist_total, rss_total, analyzed_count = self._prepare_news_content(stats, rss_stats)
        total_news = hotlist_total + rss_total

        if not news_content and not rss_content:
            return AIAnalysisResult(
                success=False,
                error="没有可分析的新闻内容",
                total_news=total_news,
                hotlist_count=hotlist_total,
                rss_count=rss_total,
                analyzed_news=0,
                max_news_limit=self.max_news
            )

        # 构建提示词
        current_time = self.get_time_func().strftime("%Y-%m-%d %H:%M:%S")

        if not keywords:
            keywords = [s.get("word", "") for s in stats if s.get("word")] if stats else []

        user_prompt = self.user_prompt_template
        user_prompt = user_prompt.replace("{report_mode}", report_mode)
        user_prompt = user_prompt.replace("{report_type}", report_type)
        user_prompt = user_prompt.replace("{current_time}", current_time)
        user_prompt = user_prompt.replace("{news_count}", str(hotlist_total))
        user_prompt = user_prompt.replace("{rss_count}", str(rss_total))
        user_prompt = user_prompt.replace("{platforms}", ", ".join(platforms) if platforms else "多平台")
        user_prompt = user_prompt.replace("{keywords}", ", ".join(keywords[:20]) if keywords else "无")
        user_prompt = user_prompt.replace("{news_content}", news_content)
        user_prompt = user_prompt.replace("{rss_content}", rss_content)
        user_prompt = user_prompt.replace("{language}", self.language)

        # 动态注入持仓信息
        if portfolio_context:
            portfolio_section = f"""
\n================ USER PORTFOLIO CONTEXT ================
{portfolio_context}
【指令】：在分析新闻时，请特别关注上述股票及其产业链上下游。
如果新闻涉及这些公司，请在生成的 JSON "stock_analysis_data" 中将其 sentiment 标记准确，
并在 core_trends 中使用【🔴 持仓关联】前缀进行高亮。
========================================================
"""
            user_prompt += portfolio_section

        # 强制注入结构化数据指令
        stock_instruction = """
\n\n================ REQUIRED JSON OUTPUT FORMAT ================
请务必返回标准的 JSON 格式，除了常规分析字段外，必须包含 "stock_analysis_data" 字段。
该字段用于量化分析，格式列表如下：
[
  {
    "title": "新闻标题",
    "summary": "简短摘要(包含了对持仓影响的分析)",
    "category": "从列表选择: [Macro, Tech, Energy, Consumer, Finance, Healthcare, Auto, Other]",
    "sentiment": "Positive 或 Negative 或 Neutral"
  }
]
=============================================================
"""
        user_prompt += stock_instruction

        # 调用 AI API
        try:
            response = self._call_ai(user_prompt)
            result = self._parse_response(response)

            if not self.include_rss:
                result.rss_insights = ""

            result.total_news = total_news
            result.hotlist_count = hotlist_total
            result.rss_count = rss_total
            result.analyzed_news = analyzed_count
            result.max_news_limit = self.max_news
            return result
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            if len(error_msg) > 200:
                error_msg = error_msg[:200] + "..."
            return AIAnalysisResult(success=False, error=f"AI 分析失败 ({error_type}): {error_msg}")

    # 🟢 关键修复：确保此方法在 AIAnalyzer 类缩进内部
    def _prepare_news_content(
        self,
        stats: List[Dict],
        rss_stats: Optional[List[Dict]] = None,
    ) -> tuple:
        """
        准备新闻内容文本
        Returns:
            tuple: (news_content, rss_content, hotlist_total, rss_total, analyzed_count)
        """
        news_lines = []
        rss_lines = []
        news_count = 0
        rss_count = 0

        hotlist_total = sum(len(s.get("titles", [])) for s in stats) if stats else 0
        rss_total = sum(len(s.get("titles", [])) for s in rss_stats) if rss_stats else 0

        # 热榜内容
        if stats:
            for stat in stats:
                word = stat.get("word", "")
                titles = stat.get("titles", [])
                if word and titles:
                    news_lines.append(f"\n**{word}** ({len(titles)}条)")
                    for t in titles[:3]: 
                        if not isinstance(t, dict): continue
                        title = t.get("title", "")
                        source = t.get("source_name", t.get("source", ""))
                        line = f"- [{source}] {title}"
                        news_lines.append(line)
                        news_count += 1
                if news_count >= self.max_news:
                    break

        # RSS 内容
        if self.include_rss and rss_stats:
            remaining = self.max_news - news_count
            if remaining > 0:
                for stat in rss_stats:
                    if rss_count >= remaining: break
                    word = stat.get("word", "")
                    titles = stat.get("titles", [])
                    if word and titles:
                        rss_lines.append(f"\n**{word}** ({len(titles)}条)")
                        for t in titles[:2]:
                            if not isinstance(t, dict): continue
                            title = t.get("title", "")
                            source = t.get("source_name", t.get("feed_name", ""))
                            line = f"- [{source}] {title}"
                            rss_lines.append(line)
                            rss_count += 1
                            if rss_count >= remaining: break

        news_content = "\n".join(news_lines) if news_lines else ""
        rss_content = "\n".join(rss_lines) if rss_lines else ""
        total_count = news_count + rss_count

        return news_content, rss_content, hotlist_total, rss_total, total_count

    def _call_ai(self, user_prompt: str) -> str:
        """调用 AI API（使用 LiteLLM）"""
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        return self.client.chat(messages)

    def _format_time_range(self, first_time: str, last_time: str) -> str:
        """格式化时间范围"""
        return f"{first_time}~{last_time}"

    def _format_rank_timeline(self, rank_timeline: List[Dict]) -> str:
        """格式化排名时间线"""
        return "-"

    def _parse_response(self, response: str) -> AIAnalysisResult:
        """解析 AI 响应"""
        result = AIAnalysisResult(raw_response=response)

        if not response or not response.strip():
            result.error = "AI 返回空响应"
            return result

        try:
            json_str = response
            if "```json" in response:
                parts = response.split("```json", 1)
                if len(parts) > 1:
                    code_block = parts[1]
                    end_idx = code_block.find("```")
                    json_str = code_block[:end_idx] if end_idx != -1 else code_block
            elif "```" in response:
                parts = response.split("```", 2)
                if len(parts) >= 2:
                    json_str = parts[1]

            json_str = json_str.strip()
            if not json_str:
                json_str = response

            data = json.loads(json_str)

            result.core_trends = data.get("core_trends", "")
            result.sentiment_controversy = data.get("sentiment_controversy", "")
            result.signals = data.get("signals", "")
            result.rss_insights = data.get("rss_insights", "")
            result.outlook_strategy = data.get("outlook_strategy", "")
            
            # === 解析股票数据 ===
            result.stock_analysis_data = data.get("stock_analysis_data", [])
            
            result.success = True

        except Exception as e:
            result.error = f"JSON 解析失败: {str(e)}"
            result.core_trends = response[:500] + "..." if len(response) > 500 else response
            result.success = True 

        return result
