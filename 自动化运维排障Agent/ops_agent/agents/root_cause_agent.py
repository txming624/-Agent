"""
根因定位Agent
负责基于日志分析结果，结合RAG知识库，定位故障根因
"""

import json
from typing import Optional

from .base import BaseAgent, AgentResult
from ..rag.knowledge_base import KnowledgeBase


SYSTEM_PROMPT = """你是一个资深的运维故障诊断专家。你的任务是基于日志分析结果，定位故障的根本原因。

你需要：
1. 综合分析日志中的错误模式
2. 结合历史故障案例（RAG检索结果）
3. 推断最可能的根本原因
4. 评估故障的严重程度和影响范围
5. 给出置信度评估

分析思路：
- 从表象错误追溯到根本原因
- 区分直接原因和间接原因
- 考虑时间维度（错误出现的先后顺序）
- 考虑依赖关系（服务之间的调用链）

输出格式要求（JSON）：
{
    "root_cause": "根本原因描述",
    "root_cause_category": "故障类别(系统/应用/网络/数据库/安全/配置)",
    "confidence": 0.85,
    "severity": "critical/high/medium/low",
    "impact_scope": "影响范围描述",
    "direct_causes": [
        {"cause": "直接原因", "evidence": "证据"}
    ],
    "contributing_factors": ["促成因素1", "促成因素2"],
    "similar_cases": ["历史相似案例引用"],
    "analysis_chain": ["分析步骤1 -> 分析步骤2 -> 结论"]
}"""


class RootCauseAgent(BaseAgent):
    """根因定位Agent"""

    def __init__(self, config, knowledge_base: Optional[KnowledgeBase] = None):
        super().__init__(config)
        self.knowledge_base = knowledge_base

    def execute(
        self,
        log_analysis: dict,
        raw_logs_summary: Optional[str] = None,
        **kwargs
    ) -> AgentResult:
        """执行根因分析"""
        self.logger.info("开始根因分析")

        try:
            # RAG检索相关历史案例
            similar_cases = self._search_similar_cases(log_analysis)

            # 构建分析输入
            user_prompt = self._build_prompt(log_analysis, similar_cases, raw_logs_summary)

            # 调用LLM分析
            response = self._call_llm(SYSTEM_PROMPT, user_prompt)
            result_data = self._parse_response(response)

            # 添加RAG检索结果
            result_data["rag_matches"] = similar_cases

            self.logger.info(f"根因分析完成: {result_data.get('root_cause', 'N/A')[:100]}")
            return AgentResult(
                success=True,
                data=result_data,
                summary=f"根因: {result_data.get('root_cause', '未确定')} (置信度: {result_data.get('confidence', 0)})"
            )

        except Exception as e:
            self.logger.error(f"根因分析失败: {e}")
            return AgentResult(
                success=False,
                error=str(e),
                summary=f"根因分析失败: {e}"
            )

    def _search_similar_cases(self, log_analysis: dict) -> list[dict]:
        """检索相似历史案例"""
        if not self.knowledge_base:
            return []

        try:
            # 构建检索查询
            query_parts = []

            if log_analysis.get("error_summary"):
                query_parts.append(log_analysis["error_summary"])

            if log_analysis.get("error_types"):
                query_parts.extend(log_analysis["error_types"])

            if log_analysis.get("key_findings"):
                query_parts.extend(log_analysis["key_findings"][:3])

            query = " ".join(query_parts)

            if not query.strip():
                return []

            results = self.knowledge_base.search(query, top_k=3)
            self.logger.info(f"RAG检索到 {len(results)} 条相关案例")
            return results

        except Exception as e:
            self.logger.warning(f"RAG检索失败: {e}")
            return []

    def _build_prompt(
        self,
        log_analysis: dict,
        similar_cases: list[dict],
        raw_logs_summary: Optional[str]
    ) -> str:
        """构建分析提示"""
        parts = ["请分析以下故障信息，定位根本原因：\n"]

        # 日志分析结果
        parts.append("## 日志分析结果")
        parts.append(json.dumps(log_analysis, ensure_ascii=False, indent=2))

        # RAG检索结果
        if similar_cases:
            parts.append("\n## 历史相似案例（供参考）")
            for i, case in enumerate(similar_cases, 1):
                parts.append(f"\n### 案例{i} (相似度: {case.get('score', 0):.2f})")
                parts.append(case.get("content", ""))

        # 原始日志摘要
        if raw_logs_summary:
            parts.append(f"\n## 原始日志摘要\n{raw_logs_summary[:3000]}")

        parts.append("\n请按照要求的JSON格式输出根因分析结果。")
        return "\n".join(parts)

    def _parse_response(self, response: str) -> dict:
        """解析LLM响应"""
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                start = response.find("{")
                end = response.rfind("}") + 1
                if start != -1 and end > start:
                    json_str = response[start:end]
                else:
                    json_str = response

            return json.loads(json_str)
        except json.JSONDecodeError:
            return {
                "root_cause": response[:500],
                "root_cause_category": "unknown",
                "confidence": 0.3,
                "severity": "medium",
                "impact_scope": "未知",
                "direct_causes": [],
                "contributing_factors": [],
                "similar_cases": [],
                "analysis_chain": []
            }
