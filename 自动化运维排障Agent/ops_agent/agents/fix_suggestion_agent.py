"""
修复建议Agent
负责基于根因分析结果，给出具体的修复方案和操作步骤
"""

import json
from typing import Optional

from .base import BaseAgent, AgentResult


SYSTEM_PROMPT = """你是一个资深的运维工程师和SRE专家。你的任务是基于故障根因分析，给出具体可执行的修复方案。

你需要：
1. 提供立即止血方案（短期修复）
2. 提供根本解决方案（长期修复）
3. 给出具体的操作命令和步骤
4. 评估修复风险和回滚方案
5. 提供预防措施避免再次发生

修复方案要求：
- 操作步骤必须具体可执行
- 包含验证方法（如何确认修复成功）
- 包含回滚方案（修复失败怎么办）
- 考虑不同环境的差异（开发/测试/生产）

输出格式要求（JSON）：
{
    "immediate_fix": {
        "description": "立即止血方案描述",
        "steps": [
            {
                "step": 1,
                "action": "操作描述",
                "command": "具体命令（如有）",
                "expected_result": "预期结果"
            }
        ],
        "estimated_time": "预计耗时",
        "risk_level": "low/medium/high"
    },
    "root_fix": {
        "description": "根本解决方案描述",
        "steps": [...],
        "estimated_time": "预计耗时",
        "requires_downtime": true/false
    },
    "verification": {
        "steps": ["验证步骤1", "验证步骤2"],
        "success_criteria": "成功标准"
    },
    "rollback": {
        "description": "回滚方案",
        "steps": ["回滚步骤1", "回滚步骤2"]
    },
    "prevention": {
        "monitoring": ["需要添加的监控项"],
        "alerts": ["需要配置的告警"],
        "best_practices": ["最佳实践建议"]
    },
    "related_commands": ["相关运维命令"],
    "references": ["参考文档链接或路径"]
}"""


class FixSuggestionAgent(BaseAgent):
    """修复建议Agent"""

    def execute(
        self,
        root_cause_analysis: dict,
        log_analysis: Optional[dict] = None,
        **kwargs
    ) -> AgentResult:
        """生成修复建议"""
        self.logger.info("开始生成修复建议")

        try:
            # 构建分析输入
            user_prompt = self._build_prompt(root_cause_analysis, log_analysis)

            # 调用LLM生成建议
            response = self._call_llm(SYSTEM_PROMPT, user_prompt)
            result_data = self._parse_response(response)

            self.logger.info("修复建议生成完成")
            return AgentResult(
                success=True,
                data=result_data,
                summary=result_data.get("immediate_fix", {}).get("description", "修复建议已生成")
            )

        except Exception as e:
            self.logger.error(f"修复建议生成失败: {e}")
            return AgentResult(
                success=False,
                error=str(e),
                summary=f"修复建议生成失败: {e}"
            )

    def _build_prompt(
        self,
        root_cause_analysis: dict,
        log_analysis: Optional[dict]
    ) -> str:
        """构建提示"""
        parts = ["请基于以下故障分析结果，生成具体的修复方案：\n"]

        # 根因分析结果
        parts.append("## 根因分析结果")
        parts.append(json.dumps(root_cause_analysis, ensure_ascii=False, indent=2))

        # 日志分析摘要
        if log_analysis:
            parts.append("\n## 日志分析摘要")
            parts.append(f"- 错误摘要: {log_analysis.get('error_summary', 'N/A')}")
            parts.append(f"- 错误类型: {', '.join(log_analysis.get('error_types', []))}")
            parts.append(f"- 受影响服务: {', '.join(log_analysis.get('affected_services', []))}")

        # RAG匹配的历史案例
        if root_cause_analysis.get("rag_matches"):
            parts.append("\n## 历史修复案例（供参考）")
            for case in root_cause_analysis["rag_matches"][:2]:
                parts.append(case.get("content", "")[:500])

        parts.append("\n请按照要求的JSON格式输出修复方案。确保命令具体可执行。")
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
                "immediate_fix": {
                    "description": response[:500],
                    "steps": [],
                    "estimated_time": "未知",
                    "risk_level": "medium"
                },
                "root_fix": {
                    "description": "需要进一步分析",
                    "steps": [],
                    "estimated_time": "未知",
                    "requires_downtime": False
                },
                "verification": {"steps": [], "success_criteria": ""},
                "rollback": {"description": "", "steps": []},
                "prevention": {"monitoring": [], "alerts": [], "best_practices": []},
                "related_commands": [],
                "references": []
            }
