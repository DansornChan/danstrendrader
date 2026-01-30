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
    
    # === 【新增】股票分析专用数据 (确保这里定义了) ===
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
        Args:
            ai_config: AI 模型配置（LiteLLM 格式）
            analysis_config: AI 分析功能配置（language, prompt_file 等）
            get_time_func: 获取当前时间的函数
            debug: 是否开启调试模式
        """
        self.ai_config = ai_config
        self.analysis_config = analysis_config
        self.get_time_func = get_time_func
        self.debug = debug

        # 创建 AI 客户端（基于 LiteLLM）
        self.client = AIClient(ai_config)

        # 验证配置
        valid, error = self.client.validate_config()
        if not valid:
            print(f"[AI] 配置警告: {error}")

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
        # 尝试寻找 config 目录
        # 假设结构是 trendradar/ai/analyzer.py -> trendradar/config/
        try:
            current_dir = Path(__file__).parent
            # 向上找，直到找到 config 目录或者到达根目录
            config_dir = None
            for parent in [current_dir.parent, current_dir.parent.parent]:
                if (parent / "config").exists():
                    config_dir = parent / "config"
                    break
            
            if not config_dir:
                # 回退到默认相对路径
                config_dir = Path(__file__).parent.parent.parent / "config"

            prompt_path = config_dir / prompt_file

            if not prompt_path.exists():
                print(f"[AI] 提示词文件不存在: {prompt_path}，将使用内置默认模板")
                return "你是一个金融分析师。", "{news_content}"

            content = prompt_path.read_text(encoding="utf-8")

            # 解析 [system] 和 [user] 部分
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
        portfolio_context: str = ""  # <--- 🆕 【修改1】新增参数接收持仓信息
    ) -> AIAnalysisResult:
        """
        执行 AI 分析
        """
        if not self.client.api_key:
            return AIAnalysisResult(
                success=False,
                error="未配置 AI API Key，请在 config.yaml 或环境变量 AI_API_KEY 中设置"
            )

        # 准备新闻内容并获取统计数据
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
