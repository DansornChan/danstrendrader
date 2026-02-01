def _parse_response(self, response: str) -> AIAnalysisResult:
    """解析 AI 响应"""
    result = AIAnalysisResult(raw_response=response)
    
    # 添加调试信息
    print(f"[AI解析] 原始响应长度: {len(response)}")
    print(f"[AI解析] 原始响应前200字符: {response[:200]}...")

    if not response or not response.strip():
        result.error = "AI 返回空响应"
        return result

    try:
        json_str = response
        
        # 提取JSON部分
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
        print(f"[AI解析] 提取的JSON字符串长度: {len(json_str)}")
        print(f"[AI解析] 提取的JSON字符串前300字符: {json_str[:300]}...")

        # 尝试解析JSON
        data = json.loads(json_str)

        # 打印解析出的字段
        print(f"[AI解析] 解析出的字段: {list(data.keys())}")
        
        result.core_trends = data.get("core_trends", "")
        result.sentiment_controversy = data.get("sentiment_controversy", "")
        result.signals = data.get("signals", "")
        result.rss_insights = data.get("rss_insights", "")
        result.outlook_strategy = data.get("outlook_strategy", "")
        result.stock_analysis_data = data.get("stock_analysis_data", [])
        
        # 打印每个字段的长度
        print(f"[AI解析] core_trends 长度: {len(result.core_trends)}")
        print(f"[AI解析] sentiment_controversy 长度: {len(result.sentiment_controversy)}")
        print(f"[AI解析] signals 长度: {len(result.signals)}")
        print(f"[AI解析] rss_insights 长度: {len(result.rss_insights)}")
        print(f"[AI解析] outlook_strategy 长度: {len(result.outlook_strategy)}")
        print(f"[AI解析] stock_analysis_data 数量: {len(result.stock_analysis_data)}")
        
        result.success = True

    except Exception as e:
        result.error = f"JSON 解析失败: {str(e)}"
        print(f"[AI解析] JSON解析异常: {e}")
        print(f"[AI解析] 异常发生时的json_str: {json_str[:500] if 'json_str' in locals() else 'N/A'}")
        
        # 如果JSON解析失败，尝试从原始响应中提取各个部分
        result.core_trends = self._extract_section(response, "核心热点态势", "舆论风向与板块情绪")
        result.sentiment_controversy = self._extract_section(response, "舆论风向与板块情绪", "异动与弱信号")
        result.signals = self._extract_section(response, "异动与弱信号", "专业场深度洞察")
        result.rss_insights = self._extract_section(response, "专业场深度洞察", "投研策略建议")
        result.outlook_strategy = self._extract_section(response, "投研策略建议", None)
        
        # 如果core_trends为空，使用原始响应
        if not result.core_trends:
            result.core_trends = response[:500] + "..." if len(response) > 500 else response
        
        result.success = True  # 仍然标记为成功，因为有兜底内容

    return result

def _extract_section(self, text: str, start_marker: str, end_marker: str = None) -> str:
    """从文本中提取指定部分"""
    try:
        start_idx = text.find(start_marker)
        if start_idx == -1:
            return ""
        
        if end_marker:
            end_idx = text.find(end_marker, start_idx + len(start_marker))
            if end_idx == -1:
                return text[start_idx:].strip()
            return text[start_idx:end_idx].strip()
        else:
            return text[start_idx:].strip()
    except Exception:
        return ""