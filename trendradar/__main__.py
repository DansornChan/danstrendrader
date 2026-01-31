# coding=utf-8
"""
TrendRadar 主程序

热点新闻聚合与分析工具
支持: python -m trendradar
"""

import os
import webbrowser
import json
import requests
import logging  # [修复] 引入 logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from difflib import SequenceMatcher

from trendradar.context import AppContext
from trendradar import __version__
from trendradar.core import load_config
from trendradar.core.analyzer import convert_keyword_stats_to_platform_stats
from trendradar.crawler import DataFetcher
from trendradar.storage import convert_crawl_results_to_news_data
from trendradar.utils.time import is_within_days
from trendradar.ai import AIAnalyzer, AIAnalysisResult

# [修复] 初始化日志记录器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def check_version_update(
    current_version: str, version_url: str, proxy_url: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """检查版本更新"""
    try:
        proxies = None
        if proxy_url:
            proxies = {"http": proxy_url, "https": proxy_url}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/plain, */*",
            "Cache-Control": "no-cache",
        }

        response = requests.get(
            version_url, proxies=proxies, headers=headers, timeout=10
        )
        response.raise_for_status()

        remote_version = response.text.strip()
        print(f"当前版本: {current_version}, 远程版本: {remote_version}")

        # 比较版本
        def parse_version(version_str):
            try:
                parts = version_str.strip().split(".")
                if len(parts) != 3:
                    raise ValueError("版本号格式不正确")
                return int(parts[0]), int(parts[1]), int(parts[2])
            except:
                return 0, 0, 0

        current_tuple = parse_version(current_version)
        remote_tuple = parse_version(remote_version)

        need_update = current_tuple < remote_tuple
        return need_update, remote_version if need_update else None

    except Exception as e:
        print(f"版本检查失败: {e}")
        return False, None


# === 主分析器 ===
class NewsAnalyzer:
    """新闻分析器"""

    # 模式策略定义
    MODE_STRATEGIES = {
        "incremental": {
            "mode_name": "增量模式",
            "description": "增量模式（只关注新增新闻，无新增时不推送）",
            "report_type": "增量分析",
            "should_send_notification": True,
        },
        "current": {
            "mode_name": "当前榜单模式",
            "description": "当前榜单模式（当前榜单匹配新闻 + 新增新闻区域 + 按时推送）",
            "report_type": "当前榜单",
            "should_send_notification": True,
        },
        "daily": {
            "mode_name": "全天汇总模式",
            "description": "全天汇总模式（所有匹配新闻 + 新增新闻区域 + 按时推送）",
            "report_type": "全天汇总",
            "should_send_notification": True,
        },
    }

    def __init__(self):
        # 加载配置
        print("正在加载配置...")
        config = load_config()
        print(f"TrendRadar v{__version__} 配置加载完成")
        print(f"监控平台数量: {len(config['PLATFORMS'])}")
        print(f"时区: {config.get('TIMEZONE', 'Asia/Shanghai')}")

        # 创建应用上下文
        self.ctx = AppContext(config)

        self.request_interval = self.ctx.config["REQUEST_INTERVAL"]
        self.report_mode = self.ctx.config["REPORT_MODE"]
        self.rank_threshold = self.ctx.rank_threshold
        self.is_github_actions = os.environ.get("GITHUB_ACTIONS") == "true"
        self.is_docker_container = self._detect_docker_environment()
        self.update_info = None
        self.proxy_url = None
        self._setup_proxy()
        self.data_fetcher = DataFetcher(self.proxy_url)

        # 初始化存储管理器（使用 AppContext）
        self._init_storage_manager()

        if self.is_github_actions:
            self._check_version_update()

    def _init_storage_manager(self) -> None:
        """初始化存储管理器（使用 AppContext）"""
        # 获取数据保留天数（支持环境变量覆盖）
        env_retention = os.environ.get("STORAGE_RETENTION_DAYS", "").strip()
        if env_retention:
            # 环境变量覆盖配置
            self.ctx.config["STORAGE"]["RETENTION_DAYS"] = int(env_retention)

        self.storage_manager = self.ctx.get_storage_manager()
        print(f"存储后端: {self.storage_manager.backend_name}")

        retention_days = self.ctx.config.get("STORAGE", {}).get("RETENTION_DAYS", 0)
        if retention_days > 0:
            print(f"数据保留天数: {retention_days} 天")

    def _detect_docker_environment(self) -> bool:
        """检测是否运行在 Docker 容器中"""
        try:
            if os.environ.get("DOCKER_CONTAINER") == "true":
                return True

            if os.path.exists("/.dockerenv"):
                return True

            return False
        except Exception:
            return False

    def _should_open_browser(self) -> bool:
        """判断是否应该打开浏览器"""
        return not self.is_github_actions and not self.is_docker_container

    # --- 🆕 新增：获取用户持仓上下文 ---
    def _fetch_portfolio_context(self) -> str:
        """
        从 GitHub 获取用户持仓配置，并生成 A 股代码识别上下文
        """
        # 这里硬编码你的仓库地址，或者你可以把它放到 config.yaml 里读取
        url = "https://raw.githubusercontent.com/DansornChan/daily_stock_analysis/main/portfolio.json"
        
        print("[Context] 正在同步持仓数据...")
        try:
            # 如果是私有库，可以在 headers 中加入 Authorization
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                # 兼容处理：如果是 list 直接用，如果是 dict 取 keys
                if isinstance(data, dict):
                    codes = list(data.keys())
                elif isinstance(data, list):
                    codes = data
                else:
                    codes = []
                
                # 过滤出 6 位数字代码 (A股特征)
                a_share_codes = [str(c) for c in codes if str(c).isdigit() and len(str(c)) == 6]
                
                if not a_share_codes:
                    return ""
                
                # 生成给 AI 的 Prompt 片段
                context = (
                    f"【用户核心持仓（中国A股）】代码列表: {', '.join(a_share_codes)}。\n"
                    f"指令：请务必根据代码（如 600406 -> 国电南瑞）识别对应的公司实体及所属行业产业链，"
                    f"若新闻涉及这些公司或其上下游，请标记为【🔴 持仓关联】。"
                )
                print(f"[Context] 成功加载 {len(a_share_codes)} 只持仓股票上下文")
                return context
            else:
                print(f"[Context] 获取持仓失败: HTTP {response.status_code}")
                return ""
        except Exception as e:
            print(f"[Context] 同步持仓出错: {e}")
            return ""

    def _export_json_for_stock_analysis(self, ai_result: AIAnalysisResult) -> None:
        """将 AI 分析结果保存为 JSON 文件"""
        try:
            output_dir = Path("output")
            output_dir.mkdir(parents=True, exist_ok=True)
            file_path = output_dir / "news_summary.json"

            # 优先使用 AI 生成的结构化数据 (stock_analysis_data)
            if ai_result.stock_analysis_data and len(ai_result.stock_analysis_data) > 0:
                data = ai_result.stock_analysis_data
                print(f"[导出] 成功提取 {len(data)} 条行业分类数据")
            else:
                # 兜底：如果没有结构化数据，就把整段文本算作 Macro
                print("[导出] 警告：AI 未返回结构化数据，使用默认兜底")
                data = [{
                    "category": "Macro",
                    "title": "市场宏观综述",
                    "summary": ai_result.core_trends[:200] + "..." if ai_result.core_trends else "无分析内容",
                    "sentiment": "Neutral"
                }]

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"[导出] Stock Analysis 专用数据已保存: {file_path}")
        except Exception as e:
            print(f"[导出] 保存 JSON 失败: {e}")

    def _setup_proxy(self) -> None:
        """设置代理配置"""
        if not self.is_github_actions and self.ctx.config["USE_PROXY"]:
            self.proxy_url = self.ctx.config["DEFAULT_PROXY"]
            print("本地环境，使用代理")
        elif not self.is_github_actions and not self.ctx.config["USE_PROXY"]:
            print("本地环境，未启用代理")
        else:
            print("GitHub Actions环境，不使用代理")

    def _check_version_update(self) -> None:
        """检查版本更新"""
        try:
            need_update, remote_version = check_version_update(
                __version__, self.ctx.config["VERSION_CHECK_URL"], self.proxy_url
            )

            if need_update and remote_version:
                self.update_info = {
                    "current_version": __version__,
                    "remote_version": remote_version,
                }
                print(f"发现新版本: {remote_version} (当前: {__version__})")
            else:
                print("版本检查完成，当前为最新版本")
        except Exception as e:
            print(f"版本检查出错: {e}")

    def _get_mode_strategy(self) -> Dict:
        """获取当前模式的策略配置"""
        return self.MODE_STRATEGIES.get(self.report_mode, self.MODE_STRATEGIES["daily"])

    def _has_notification_configured(self) -> bool:
        """检查是否配置了任何通知渠道"""
        cfg = self.ctx.config
        return any(
            [
                cfg["FEISHU_WEBHOOK_URL"],
                cfg["DINGTALK_WEBHOOK_URL"],
                cfg["WEWORK_WEBHOOK_URL"],
                (cfg["TELEGRAM_BOT_TOKEN"] and cfg["TELEGRAM_CHAT_ID"]),
                (
                    cfg["EMAIL_FROM"]
                    and cfg["EMAIL_PASSWORD"]
                    and cfg["EMAIL_TO"]
                ),
                (cfg["NTFY_SERVER_URL"] and cfg["NTFY_TOPIC"]),
                cfg["BARK_URL"],
                cfg["SLACK_WEBHOOK_URL"],
                cfg["GENERIC_WEBHOOK_URL"],
            ]
        )

    def _has_valid_content(
        self, stats: List[Dict], new_titles: Optional[Dict] = None
    ) -> bool:
        """检查是否有有效的新闻内容"""
        if self.report_mode == "incremental":
            # 增量模式：必须有新增标题且匹配了关键词才推送
            has_new_titles = bool(
                new_titles and any(len(titles) > 0 for titles in new_titles.values())
            )
            has_matched_news = any(stat["count"] > 0 for stat in stats)
            return has_new_titles and has_matched_news
        elif self.report_mode == "current":
            # current模式：只要stats有内容就说明有匹配的新闻
            return any(stat["count"] > 0 for stat in stats)
        else:
            # 当日汇总模式下，检查是否有匹配的频率词新闻或新增新闻
            has_matched_news = any(stat["count"] > 0 for stat in stats)
            has_new_news = bool(
                new_titles and any(len(titles) > 0 for titles in new_titles.values())
            )
            return has_matched_news or has_new_news

    def _run_ai_analysis(
        self,
        stats: List[Dict],
        rss_items: Optional[List[Dict]],
        mode: str,
        report_type: str,
        id_to_name: Optional[Dict],
    ) -> Optional[AIAnalysisResult]:
        """执行 AI 分析"""
        analysis_config = self.ctx.config.get("AI_ANALYSIS", {})
        if not analysis_config.get("ENABLED", False):
            return None

        print("[AI] 正在进行 AI 分析...")
        try:
            # 1. 获取持仓上下文 (新增逻辑)
            portfolio_context = self._fetch_portfolio_context()

            ai_config = self.ctx.config.get("AI", {})
            debug_mode = self.ctx.config.get("DEBUG", False)
            analyzer = AIAnalyzer(ai_config, analysis_config, self.ctx.get_time, debug=debug_mode)

            # 提取平台列表
            platforms = list(id_to_name.values()) if id_to_name else []

            # 提取关键词列表
            keywords = [s.get("word", "") for s in stats if s.get("word")] if stats else []

            # 2. 传递 portfolio_context 给分析器
            result = analyzer.analyze(
                stats=stats,
                rss_stats=rss_items,
                report_mode=mode,
                report_type=report_type,
                platforms=platforms,
                keywords=keywords,
                portfolio_context=portfolio_context  # 👈 关键注入点
            )

            if result.success:
                if result.error:
                    # 成功但有警告（如 JSON 解析问题但使用了原始文本）
                    print(f"[AI] 分析完成（有警告: {result.error}）")
                else:
                    print("[AI] 分析完成")
            else:
                print(f"[AI] 分析失败: {result.error}")

            return result
        except Exception as e:
            import traceback
            error_type = type(e).__name__
            error_msg = str(e)
            # 截断过长的错误消息
            if len(error_msg) > 200:
                error_msg = error_msg[:200] + "..."
            print(f"[AI] 分析出错 ({error_type}): {error_msg}")
            # 详细错误日志到 stderr
            import sys
            print(f"[AI] 详细错误堆栈:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return AIAnalysisResult(success=False, error=f"{error_type}: {error_msg}")

    def _load_analysis_data(
        self,
        quiet: bool = False,
    ) -> Optional[Tuple[Dict, Dict, Dict, Dict, List, List]]:
        """统一的数据加载和预处理，使用当前监控平台列表过滤历史数据"""
        try:
            # 获取当前配置的监控平台ID列表
            current_platform_ids = self.ctx.platform_ids
            if not quiet:
                print(f"当前监控平台: {current_platform_ids}")

            all_results, id_to_name, title_info = self.ctx.read_today_titles(
                current_platform_ids, quiet=quiet
            )

            if not all_results:
                print("没有找到当天的数据")
                return None

            total_titles = sum(len(titles) for titles in all_results.values())
            if not quiet:
                print(f"读取到 {total_titles} 个标题（已按当前监控平台过滤）")

            new_titles = self.ctx.detect_new_titles(current_platform_ids, quiet=quiet)
            word_groups, filter_words, global_filters = self.ctx.load_frequency_words()

            return (
                all_results,
                id_to_name,
                title_info,
                new_titles,
                word_groups,
                filter_words,
                global_filters,
            )
        except Exception as e:
            print(f"数据加载失败: {e}")
            return None

    def _prepare_current_title_info(self, results: Dict, time_info: str) -> Dict:
        """从当前抓取结果构建标题信息"""
        title_info = {}
        for source_id, titles_data in results.items():
            title_info[source_id] = {}
            for title, title_data in titles_data.items():
                ranks = title_data.get("ranks", [])
                url = title_data.get("url", "")
                mobile_url = title_data.get("mobileUrl", "")

                title_info[source_id][title] = {
                    "first_time": time_info,
                    "last_time": time_info,
                    "count": 1,
                    "ranks": ranks,
                    "url": url,
                    "mobileUrl": mobile_url,
                }
        return title_info

    def _prepare_standalone_data(
        self,
        results: Dict,
        id_to_name: Dict,
        title_info: Optional[Dict] = None,
        rss_items: Optional[List[Dict]] = None,
    ) -> Optional[Dict]:
        """
        从原始数据中提取独立展示区数据
        """
        display_config = self.ctx.config.get("DISPLAY", {})
        regions = display_config.get("REGIONS", {})
        standalone_config = display_config.get("STANDALONE", {})

        if not regions.get("STANDALONE", False):
            return None

        platform_ids = standalone_config.get("PLATFORMS", [])
        rss_feed_ids = standalone_config.get("RSS_FEEDS", [])
        max_items = standalone_config.get("MAX_ITEMS", 20)

        if not platform_ids and not rss_feed_ids:
            return None

        standalone_data = {
            "platforms": [],
            "rss_feeds": [],
        }

        # 找出最新批次时间
        latest_time = None
        if title_info:
            for source_titles in title_info.values():
                for title_data in source_titles.values():
                    last_time = title_data.get("last_time", "")
                    if last_time:
                        if latest_time is None or last_time > latest_time:
                            latest_time = last_time

        # 提取热榜平台数据
        for platform_id in platform_ids:
            if platform_id not in results:
                continue

            platform_name = id_to_name.get(platform_id, platform_id)
            platform_titles = results[platform_id]

            items = []
            for title, title_data in platform_titles.items():
                meta = {}
                if title_info and platform_id in title_info and title in title_info[platform_id]:
                    meta = title_info[platform_id][title]

                if latest_time and meta:
                    if meta.get("last_time") != latest_time:
                        continue

                current_ranks = title_data.get("ranks", [])
                current_rank = current_ranks[-1] if current_ranks else 0

                historical_ranks = meta.get("ranks", []) if meta else []
                all_ranks = historical_ranks.copy()
                for rank in current_ranks:
                    if rank not in all_ranks:
                        all_ranks.append(rank)
                display_ranks = all_ranks if all_ranks else current_ranks

                item = {
                    "title": title,
                    "url": title_data.get("url", ""),
                    "mobileUrl": title_data.get("mobileUrl", ""),
                    "rank": current_rank,
                    "ranks": display_ranks,
                    "first_time": meta.get("first_time", ""),
                    "last_time": meta.get("last_time", ""),
                    "count": meta.get("count", 1),
                }
                items.append(item)

            items.sort(key=lambda x: x["rank"] if x["rank"] > 0 else 9999)

            if max_items > 0:
                items = items[:max_items]

            if items:
                standalone_data["platforms"].append({
                    "id": platform_id,
                    "name": platform_name,
                    "items": items,
                })

        # 提取 RSS 数据
        if rss_items and rss_feed_ids:
            feed_items_map = {}
            for item in rss_items:
                feed_id = item.get("feed_id", "")
                if feed_id in rss_feed_ids:
                    if feed_id not in feed_items_map:
                        feed_items_map[feed_id] = {
                            "name": item.get("feed_name", feed_id),
                            "items": [],
                        }
                    feed_items_map[feed_id]["items"].append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "published_at": item.get("published_at", ""),
                        "author": item.get("author", ""),
                    })

            for feed_id in rss_feed_ids:
                if feed_id in feed_items_map:
                    feed_data = feed_items_map[feed_id]
                    items = feed_data["items"]
                    if max_items > 0:
                        items = items[:max_items]
                    if items:
                        standalone_data["rss_feeds"].append({
                            "id": feed_id,
                            "name": feed_data["name"],
                            "items": items,
                        })

        if not standalone_data["platforms"] and not standalone_data["rss_feeds"]:
            return None

        return standalone_data

    def _deduplicate_items(self, items_list: List[Dict]) -> List[Dict]:
        """
        核心去重逻辑：标题相似度 > 0.7 的视为同一条新闻，合并频次。
        同时执行 max_news_per_keyword 截断。
        """
        from difflib import SequenceMatcher
        if not items_list:
            return []

        deduped = []
        for item in items_list:
            found = False
            title = item.get('title', '')
            
            for exist in deduped:
                # 语义相似度检查
                similarity = SequenceMatcher(None, title, exist['title']).ratio()
                if similarity > 0.7:
                    # 合并逻辑：增加计数，合并排名
                    exist['count'] = exist.get('count', 1) + 1
                    if 'ranks' in item and 'ranks' in exist:
                        # 合并去重排名
                        combined_ranks = list(set(exist['ranks'] + item['ranks']))
                        exist['ranks'] = sorted(combined_ranks)
                    found = True
                    break
            
            if not found:
                # 如果没找到相似的，设置初始 count 为 1
                if 'count' not in item:
                    item['count'] = 1
                deduped.append(item)
        
        # === 新增：强制执行数量限制 ===
        # 读取配置中的限制，默认 3 条
        limit = self.ctx.config.get("REPORT", {}).get("MAX_NEWS_PER_KEYWORD", 3)
        if limit > 0 and len(deduped) > limit:
            deduped = deduped[:limit]
            
        return deduped

    def _run_analysis_pipeline(
        self,
        data_source: Dict,
        mode: str,
        title_info: Dict,
        new_titles: Dict,
        word_groups: List[Dict],
        filter_words: List[str],
        id_to_name: Dict,
        failed_ids: Optional[List] = None,
        global_filters: Optional[List[str]] = None,
        quiet: bool = False,
        rss_items: Optional[List[Dict]] = None,
        rss_new_items: Optional[List[Dict]] = None,
        standalone_data: Optional[Dict] = None,
    ) -> Tuple[List[Dict], Optional[str], Optional[AIAnalysisResult]]:
        """统一的分析流水线"""

        # 统计计算
        stats, total_titles = self.ctx.count_frequency(
            data_source,
            word_groups,
            filter_words,
            id_to_name,
            title_info,
            new_titles,
            mode=mode,
            global_filters=global_filters,
            quiet=quiet,
        )

        # === 核心优化：对统计后的 titles 进行语义去重 ===
        if stats:
            for group in stats:
                if 'titles' in group and group['titles']:
                    original_len = len(group['titles'])
                    group['titles'] = self._deduplicate_items(group['titles'])
                    new_len = len(group['titles'])
                    if not quiet and original_len != new_len:
                        print(f"[优化] 关键词 '{group.get('word')}' 下标题去重: {original_len} -> {new_len}")

        # 如果是 platform 模式，转换数据结构
        if self.ctx.display_mode == "platform" and stats:
            stats = convert_keyword_stats_to_platform_stats(
                stats,
                self.ctx.weight_config,
                self.ctx.rank_threshold,
            )

        # AI 分析
        ai_result = None
        ai_config = self.ctx.config.get("AI_ANALYSIS", {})
        if ai_config.get("ENABLED", False) and stats:
            mode_strategy = self._get_mode_strategy()
            report_type = mode_strategy["report_type"]
            ai_result = self._run_ai_analysis(
                stats, rss_items, mode, report_type, id_to_name
            )

        # HTML生成
        html_file = None
        if self.ctx.config["STORAGE"]["FORMATS"]["HTML"]:
            html_file = self.ctx.generate_html(
                stats,
                total_titles,
                failed_ids=failed_ids,
                new_titles=new_titles,
                id_to_name=id_to_name,
                mode=mode,
                update_info=self.update_info if self.ctx.config["SHOW_VERSION_UPDATE"] else None,
                rss_items=rss_items,
                rss_new_items=rss_new_items,
                ai_analysis=ai_result,
                standalone_data=standalone_data,
            )

        return stats, html_file, ai_result

    def _send_notification_if_needed(
        self,
        stats: List[Dict],
        report_type: str,
        mode: str,
        failed_ids: Optional[List] = None,
        new_titles: Optional[Dict] = None,
        id_to_name: Optional[Dict] = None,
        html_file_path: Optional[str] = None,
        rss_items: Optional[List[Dict]] = None,
        rss_new_items: Optional[List[Dict]] = None,
        standalone_data: Optional[Dict] = None,
        ai_result: Optional[AIAnalysisResult] = None,
    ) -> bool:
        """统一的通知发送逻辑"""
        has_notification = self._has_notification_configured()
        cfg = self.ctx.config

        # ---------------------------------------------------------------
        # 1. AI 分析：必须使用【完整数据】(包含弱信号)
        # ---------------------------------------------------------------
        if ai_result is None:
            ai_config = cfg.get("AI_ANALYSIS", {})
            if ai_config.get("ENABLED", False):
                # 这里传入的是 stats 全量数据，确保 AI 能看到排名靠后的弱信号
                ai_result = self._run_analysis_pipeline(
                    stats, rss_items, mode, report_type, id_to_name
                )

        # ---------------------------------------------------------------
        # 2. 列表展示：构建【精简数据】(隐藏弱信号)
        # ---------------------------------------------------------------
        filtered_stats_for_display = []
        if stats:
            for group in stats:
                titles = group.get('titles', [])
                if not titles:
                    continue
                
                is_strong = len(titles) >= 2
                if not is_strong:
                    # 检查排名，如果没有排名数据(rank=0)，默认视为弱
                    top_rank = titles[0].get('rank', 999)
                    if top_rank > 0 and top_rank <= 10:
                        is_strong = True
                
                if is_strong:
                    filtered_stats_for_display.append(group)

        # ---------------------------------------------------------------
        # 3. 生成报告并推送
        # ---------------------------------------------------------------
        report_data = self.ctx.prepare_report(filtered_stats_for_display, failed_ids, new_titles, id_to_name, mode)
        
        update_info_to_send = self.update_info if cfg["SHOW_VERSION_UPDATE"] else None

        has_news_content = self._has_valid_content(filtered_stats_for_display, new_titles)
        has_rss_content = bool(rss_items and len(rss_items) > 0)
        has_any_content = has_news_content or has_rss_content

        if cfg["ENABLE_NOTIFICATION"] and has_notification and has_any_content:
            # 输出推送内容统计
            news_count = sum(len(stat.get("titles", [])) for stat in filtered_stats_for_display)
            rss_count = sum(stat.get("count", 0) for stat in rss_items) if rss_items else 0
            
            content_parts = []
            if news_count > 0:
                content_parts.append(f"热榜 {news_count} 条")
            if rss_count > 0:
                content_parts.append(f"RSS {rss_count} 条")
            total_count = news_count + rss_count
            print(f"[推送] 准备发送：{' + '.join(content_parts)}，合计 {total_count} 条")

            # 推送窗口控制
            if cfg["PUSH_WINDOW"]["ENABLED"]:
                push_manager = self.ctx.create_push_manager()
                time_range_start = cfg["PUSH_WINDOW"]["TIME_RANGE"]["START"]
                time_range_end = cfg["PUSH_WINDOW"]["TIME_RANGE"]["END"]

                if not push_manager.is_in_time_range(time_range_start, time_range_end):
                    now = self.ctx.get_time()
                    print(f"推送窗口控制：当前时间 {now.strftime('%H:%M')} 不在推送时间窗口 {time_range_start}-{time_range_end} 内，跳过推送")
                    return False

                if cfg["PUSH_WINDOW"]["ONCE_PER_DAY"]:
                    if push_manager.has_pushed_today():
                        print(f"推送窗口控制：今天已推送过，跳过本次推送")
                        return False

            dispatcher = self.ctx.create_notification_dispatcher()
            results = dispatcher.dispatch_all(
                report_data=report_data,
                report_type=report_type,
                update_info=update_info_to_send,
                proxy_url=self.proxy_url,
                mode=mode,
                html_file_path=html_file_path,
                rss_items=rss_items,
                rss_new_items=rss_new_items,
                ai_analysis=ai_result, 
                standalone_data=standalone_data,
            )

            if results and any(results.values()) and cfg["PUSH_WINDOW"]["ENABLED"] and cfg["PUSH_WINDOW"]["ONCE_PER_DAY"]:
                push_manager = self.ctx.create_push_manager()
                push_manager.record_push(report_type)

            return True
        elif cfg["ENABLE_NOTIFICATION"] and has_notification and not has_any_content:
             print(f"跳过{report_type}通知：经筛选后未检测到匹配的强信号新闻")

        return False

    def _initialize_and_check_config(self) -> None:
        """通用初始化和配置检查"""
        now = self.ctx.get_time()
        print(f"当前北京时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")

        if not self.ctx.config["ENABLE_CRAWLER"]:
            print("爬虫功能已禁用，程序退出")
            return

        has_notification = self._has_notification_configured()
        if not self.ctx.config["ENABLE_NOTIFICATION"]:
            print("通知功能已禁用，将只进行数据抓取")
        elif not has_notification:
            print("未配置任何通知渠道，将只进行数据抓取，不发送通知")

        mode_strategy = self._get_mode_strategy()
        print(f"报告模式: {self.report_mode}")
        print(f"运行模式: {mode_strategy['description']}")

    def _crawl_data(self) -> Tuple[Dict, Dict, List]:
        """执行数据爬取"""
        ids = []
        for platform in self.ctx.platforms:
            if "name" in platform:
                ids.append((platform["id"], platform["name"]))
            else:
                ids.append(platform["id"])

        print(f"开始爬取数据，监控平台: {[p.get('name', p['id']) for p in self.ctx.platforms]}")
        Path("output").mkdir(parents=True, exist_ok=True)

        results, id_to_name, failed_ids = self.data_fetcher.crawl_websites(
            ids, self.request_interval
        )

        crawl_time = self.ctx.format_time()
        crawl_date = self.ctx.format_date()
        news_data = convert_crawl_results_to_news_data(
            results, id_to_name, failed_ids, crawl_time, crawl_date
        )

        if self.storage_manager.save_news_data(news_data):
            print(f"数据已保存到存储后端: {self.storage_manager.backend_name}")

        if self.ctx.config["STORAGE"]["FORMATS"]["TXT"]:
            self.ctx.save_titles(results, id_to_name, failed_ids)

        return results, id_to_name, failed_ids

    def _crawl_rss_data(self) -> Tuple[Optional[List[Dict]], Optional[List[Dict]], Optional[List[Dict]]]:
        """执行 RSS 数据抓取"""
        if not self.ctx.rss_enabled:
            return None, None, None

        rss_feeds = self.ctx.rss_feeds
        if not rss_feeds:
            return None, None, None

        try:
            from trendradar.crawler.rss import RSSFetcher, RSSFeedConfig
            feeds = []
            for feed_config in rss_feeds:
                max_age_days = None
                if feed_config.get("max_age_days") is not None:
                    max_age_days = int(feed_config["max_age_days"])

                feed = RSSFeedConfig(
                    id=feed_config.get("id", ""),
                    name=feed_config.get("name", ""),
                    url=feed_config.get("url", ""),
                    max_items=feed_config.get("max_items", 50),
                    enabled=feed_config.get("enabled", True),
                    max_age_days=max_age_days,
                )
                if feed.id and feed.url and feed.enabled:
                    feeds.append(feed)

            if not feeds:
                return None, None, None

            rss_config = self.ctx.rss_config
            rss_proxy_url = rss_config.get("PROXY_URL", "") or self.proxy_url or ""
            fetcher = RSSFetcher(
                feeds=feeds,
                request_interval=rss_config.get("REQUEST_INTERVAL", 2000),
                timeout=rss_config.get("TIMEOUT", 15),
                use_proxy=rss_config.get("USE_PROXY", False),
                proxy_url=rss_proxy_url,
                timezone=self.ctx.config.get("TIMEZONE", "Asia/Shanghai"),
                freshness_enabled=rss_config.get("FRESHNESS_FILTER", {}).get("ENABLED", True),
                default_max_age_days=rss_config.get("FRESHNESS_FILTER", {}).get("MAX_AGE_DAYS", 3),
            )

            rss_data = fetcher.fetch_all()
            if self.storage_manager.save_rss_data(rss_data):
                return self._process_rss_data_by_mode(rss_data)
            return None, None, None

        except Exception as e:
            print(f"[RSS] 抓取失败: {e}")
            return None, None, None

    def _process_rss_data_by_mode(self, rss_data) -> Tuple[Optional[List[Dict]], Optional[List[Dict]], Optional[List[Dict]]]:
        """处理 RSS 数据（按模式过滤）"""
        from trendradar.core.analyzer import count_rss_frequency
        rss_display_enabled = self.ctx.config.get("DISPLAY", {}).get("REGIONS", {}).get("RSS", True)

        try:
            word_groups, filter_words, global_filters = self.ctx.load_frequency_words()
        except FileNotFoundError:
            word_groups, filter_words, global_filters = [], [], []

        raw_rss_items = None
        new_items_dict = self.storage_manager.detect_new_rss_items(rss_data)
        new_items_list = self._convert_rss_items_to_list(new_items_dict, rss_data.id_to_name) if new_items_dict else None

        if self.report_mode == "incremental":
            raw_rss_items = new_items_list
        elif self.report_mode == "current":
            latest_data = self.storage_manager.get_latest_rss_data(rss_data.date)
            if latest_data:
                raw_rss_items = self._convert_rss_items_to_list(latest_data.items, latest_data.id_to_name)
        else:
            all_data = self.storage_manager.get_rss_data(rss_data.date)
            if all_data:
                raw_rss_items = self._convert_rss_items_to_list(all_data.items, all_data.id_to_name)

        if not rss_display_enabled:
            return None, None, raw_rss_items

        rss_stats = None
        rss_new_stats = None
        if raw_rss_items:
            rss_stats, _ = count_rss_frequency(
                rss_items=raw_rss_items,
                word_groups=word_groups,
                filter_words=filter_words,
                global_filters=global_filters,
                new_items=new_items_list,
                max_news_per_keyword=self.ctx.config.get("MAX_NEWS_PER_KEYWORD", 0),
                sort_by_position_first=self.ctx.config.get("SORT_BY_POSITION_FIRST", False),
                timezone=self.ctx.timezone,
                rank_threshold=self.rank_threshold,
                quiet=False,
            )
            if rss_stats:
                for group in rss_stats:
                    if 'titles' in group:
                        group['titles'] = self._deduplicate_items(group['titles'])

        return rss_stats, rss_new_stats, raw_rss_items

    def _convert_rss_items_to_list(self, items_dict: Dict, id_to_name: Dict) -> List[Dict]:
        """将 RSS 条目字典转换为列表格式"""
        rss_items = []
        rss_config = self.ctx.rss_config
        freshness_enabled = rss_config.get("FRESHNESS_FILTER", {}).get("ENABLED", True)
        default_max_age_days = rss_config.get("FRESHNESS_FILTER", {}).get("MAX_AGE_DAYS", 3)
        timezone = self.ctx.config.get("TIMEZONE", "Asia/Shanghai")

        for feed_id, items in items_dict.items():
            for item in items:
                if freshness_enabled and item.published_at:
                    if not is_within_days(item.published_at, default_max_age_days, timezone):
                        continue
                rss_items.append({
                    "title": item.title,
                    "feed_id": feed_id,
                    "feed_name": id_to_name.get(feed_id, feed_id),
                    "url": item.url,
                    "published_at": item.published_at,
                    "summary": item.summary,
                    "author": item.author,
                })
        return rss_items

    def _execute_mode_strategy(
        self, mode_strategy: Dict, results: Dict, id_to_name: Dict, failed_ids: List,
        rss_items: Optional[List[Dict]] = None,
        rss_new_items: Optional[List[Dict]] = None,
        raw_rss_items: Optional[List[Dict]] = None,
    ) -> Optional[str]:
        """执行模式特定逻辑"""
        current_platform_ids = self.ctx.platform_ids
        word_groups, filter_words, global_filters = self.ctx.load_frequency_words()

        html_file = None
        stats = []
        ai_result = None
        title_info = None
        new_titles = self.ctx.detect_new_titles(current_platform_ids)

        # 加载历史/当日全量数据
        analysis_data = self._load_analysis_data()
        if analysis_data:
            (all_results, h_id_to_name, h_title_info, h_new_titles, _, _, _) = analysis_data
            
            # 合并 ID 映射
            combined_id_to_name = {**h_id_to_name, **id_to_name}
            
            # 处理独立展示区数据
            standalone_data = self._prepare_standalone_data(
                all_results if self.report_mode in ["current", "daily"] else results,
                combined_id_to_name,
                h_title_info if self.report_mode in ["current", "daily"] else None,
                raw_rss_items
            )

            # 调用分析流水线
            stats, html_file, ai_result = self._run_analysis_pipeline(
                all_results if self.report_mode in ["current", "daily"] else results,
                self.report_mode,
                h_title_info if self.report_mode in ["current", "daily"] else self._prepare_current_title_info(results, self.ctx.format_time()),
                h_new_titles if self.report_mode in ["current", "daily"] else new_titles,
                word_groups,
                filter_words,
                combined_id_to_name,
                failed_ids=failed_ids,
                global_filters=global_filters,
                rss_items=rss_items,
                rss_new_items=rss_new_items,
                standalone_data=standalone_data,
            )
            
            # === JSON 导出兜底逻辑 ===
            if ai_result: 
                self._export_json_for_stock_analysis(ai_result)
            else:
                print("[系统] 未触发 AI 分析，生成兜底 JSON 文件...")
                dummy_result = AIAnalysisResult(success=True, core_trends="无重大市场异动")
                self._export_json_for_stock_analysis(dummy_result)
            
            # === [修复] 尝试保存 AI 分析结果到远程存储 ===
            # 使用正确的 save_ai_result 方法，而不是错误的 save_daily_trends
            if ai_result and hasattr(self.storage_manager, "save_ai_result"):
                try:
                    # 将 AI 结果对象转换为字典以便存储
                    ai_data_dict = {
                        "core_trends": ai_result.core_trends,
                        "industry_analysis": ai_result.stock_analysis_data, # 映射到 industry
                        "market_sentiment": getattr(ai_result, "sentiment", "Neutral"),
                        "raw_json": self._export_json_for_stock_analysis(ai_result) # 复用导出逻辑
                    }
                    self.storage_manager.save_ai_result(self.ctx.format_date(), ai_data_dict)
                    print(f"[存储] AI 分析结果已保存到 {self.storage_manager.backend_name}")
                except Exception as e:
                    logger.warning(f"[存储] 保存 AI 结果失败: {e}")
            
            # 发送通知
            if mode_strategy["should_send_notification"]:
                self._send_notification_if_needed(
                    stats, mode_strategy["report_type"], self.report_mode,
                    failed_ids=failed_ids, new_titles=h_new_titles, id_to_name=combined_id_to_name,
                    html_file_path=html_file, rss_items=rss_items, rss_new_items=rss_new_items,
                    standalone_data=standalone_data, ai_result=ai_result,
                )

        if self._should_open_browser() and html_file:
            webbrowser.open("file://" + str(Path(html_file).resolve()))

        return html_file

    def run(self) -> None:
        """执行分析流程"""
        try:
            self._initialize_and_check_config()
            mode_strategy = self._get_mode_strategy()
            results, id_to_name, failed_ids = self._crawl_data()
            rss_items, rss_new_items, raw_rss_items = self._crawl_rss_data()
            self._execute_mode_strategy(
                mode_strategy, results, id_to_name, failed_ids,
                rss_items=rss_items, rss_new_items=rss_new_items,
                raw_rss_items=raw_rss_items
            )
        except Exception as e:
            print(f"流程执行出错: {e}")
            if self.ctx.config.get("DEBUG", False): raise
        finally:
            self.ctx.cleanup()


def main():
    """主程序入口"""
    try:
        analyzer = NewsAnalyzer()
        analyzer.run()
    except Exception as e:
        print(f"❌ 程序运行错误: {e}")


if __name__ == "__main__":
    main()
