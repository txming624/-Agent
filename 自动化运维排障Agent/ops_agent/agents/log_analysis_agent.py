"""
日志分析Agent
负责从原始日志中提取关键信息、识别异常模式、分类错误类型
"""

import json
from typing import Optional

from .base import BaseAgent, AgentResult
from ..collectors.log_collector import LogEntry
from ..utils import extract_error_patterns


SYSTEM_PROMPT = """你是一个专业的日志分析专家。你的任务是分析运维日志，提取关键信息。

你需要：
1. 识别日志中的错误模式和异常
2. 提取关键时间线（故障发生的时间点）
3. 分类错误类型（系统级/应用级/网络级/数据库级）
4. 统计各类型错误的频率
5. 识别关联事件（多个服务同时出错）

输出格式要求（JSON）：
{
    "error_summary": "简要描述发现的错误",
    "error_types": ["错误类型1", "错误类型2"],
    "timeline": [
        {"time": "时间点", "event": "事件描述", "severity": "high/medium/low"}
    ],
    "affected_services": ["受影响的服务"],
    "error_frequency": {"错误类型": 数量},
    "key_findings": ["关键发现1", "关键发现2"],
    "anomalies": ["异常模式描述"]
}"""


class LogAnalysisAgent(BaseAgent):
    """日志分析Agent"""

    def execute(
        self,
        logs: list[LogEntry],
        context: Optional[str] = None,
        **kwargs
    ) -> AgentResult:
        """分析日志"""
        self.logger.info(f"开始分析 {len(logs)} 条日志")

        try:
            if not logs:
                return AgentResult(
                    success=True,
                    data={"error_summary": "没有日志数据"},
                    summary="没有提供日志数据进行分析"
                )

            # 预处理：提取错误模式
            log_messages = [log.message for log in logs]
            error_patterns = extract_error_patterns(log_messages)

            # 构建日志摘要
            log_text = self._build_log_summary(logs)

            # 调用LLM分析
            user_prompt = f"""请分析以下运维日志：

## 日志摘要（共{len(logs)}条）
{log_text}

## 预提取的错误模式统计
{json.dumps(error_patterns, ensure_ascii=False, indent=2)}

{"## 额外上下文" + chr(10) + context if context else ""}

请按照要求的JSON格式输出分析结果。"""

            response = self._call_llm(SYSTEM_PROMPT, user_prompt)
            result_data = self._parse_response(response)

            self.logger.info("日志分析完成")
            return AgentResult(
                success=True,
                data=result_data,
                summary=result_data.get("error_summary", "日志分析完成")
            )

        except Exception as e:
            self.logger.error(f"日志分析失败: {e}")
            return AgentResult(
                success=False,
                error=str(e),
                summary=f"日志分析失败: {e}"
            )

    def _build_log_summary(self, logs: list[LogEntry], max_lines: int = 200) -> str:
        """构建日志摘要"""
        # 按级别分组
        by_level = {}
        for log in logs:
            level = log.level.upper()
            if level not in by_level:
                by_level[level] = []
            by_level[level].append(log)

        summary_parts = []

        # 级别统计
        summary_parts.append("### 日志级别统计")
        for level, entries in sorted(by_level.items()):
            summary_parts.append(f"- {level}: {len(entries)}条")

        # 错误和警告日志（重点展示）
        for level in ["ERROR", "CRITICAL", "FATAL", "WARN", "WARNING"]:
            if level in by_level:
                entries = by_level[level]
                summary_parts.append(f"\n### {level}级别日志（最新{min(20, len(entries))}条）")
                for log in entries[-20:]:
                    ts = log.timestamp.strftime("%H:%M:%S") if log.timestamp else "N/A"
                    summary_parts.append(f"[{ts}] {log.message[:300]}")

        # 最近的日志
        recent = logs[-50:]
        summary_parts.append(f"\n### 最近{len(recent)}条日志")
        for log in recent:
            ts = log.timestamp.strftime("%H:%M:%S") if log.timestamp else "N/A"
            summary_parts.append(f"[{ts}] [{log.level}] {log.message[:200]}")

        result = "\n".join(summary_parts)
        return result[:8000]  # 限制长度

    def _parse_response(self, response: str) -> dict:
        """解析LLM响应"""
        try:
            # 尝试提取JSON
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                # 尝试找到JSON对象
                start = response.find("{")
                end = response.rfind("}") + 1
                if start != -1 and end > start:
                    json_str = response[start:end]
                else:
                    json_str = response

            return json.loads(json_str)
        except json.JSONDecodeError:
            return {
                "error_summary": response[:500],
                "error_types": [],
                "timeline": [],
                "affected_services": [],
                "error_frequency": {},
                "key_findings": [response[:500]],
                "anomalies": []
            }
