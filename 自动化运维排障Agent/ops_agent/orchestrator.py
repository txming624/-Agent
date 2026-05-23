"""
Agent编排器
负责协调日志采集、日志分析、根因定位、修复建议的执行流程
"""

import json
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

from .log_analysis_agent import LogAnalysisAgent
from .root_cause_agent import RootCauseAgent
from .fix_suggestion_agent import FixSuggestionAgent
from .base import AgentResult
from ..config import AppConfig
from ..collectors.log_collector import LogCollector, LogEntry, create_collector
from ..rag.knowledge_base import KnowledgeBase
from ..utils import setup_logger


@dataclass
class DiagnosisResult:
    """诊断结果"""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    log_analysis: Optional[dict] = None
    root_cause: Optional[dict] = None
    fix_suggestion: Optional[dict] = None
    logs_count: int = 0
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "logs_count": self.logs_count,
            "success": self.success,
            "error": self.error,
            "log_analysis": self.log_analysis,
            "root_cause": self.root_cause,
            "fix_suggestion": self.fix_suggestion,
        }

    def generate_report(self, format: str = "markdown") -> str:
        """生成诊断报告"""
        if format == "markdown":
            return self._generate_markdown_report()
        else:
            return self._generate_text_report()

    def _generate_markdown_report(self) -> str:
        """生成Markdown报告"""
        lines = [
            "# 🔧 运维故障诊断报告",
            "",
            f"**诊断时间**: {self.timestamp}",
            f"**分析日志数**: {self.logs_count}",
            f"**诊断状态**: {'✅ 成功' if self.success else '❌ 失败'}",
            "",
        ]

        # 日志分析部分
        if self.log_analysis:
            lines.extend([
                "## 📊 日志分析",
                "",
                f"**错误摘要**: {self.log_analysis.get('error_summary', 'N/A')}",
                "",
                "### 错误类型",
            ])
            for et in self.log_analysis.get("error_types", []):
                lines.append(f"- {et}")

            if self.log_analysis.get("affected_services"):
                lines.extend(["", "### 受影响服务"])
                for svc in self.log_analysis["affected_services"]:
                    lines.append(f"- {svc}")

            if self.log_analysis.get("key_findings"):
                lines.extend(["", "### 关键发现"])
                for finding in self.log_analysis["key_findings"]:
                    lines.append(f"- {finding}")

            if self.log_analysis.get("timeline"):
                lines.extend(["", "### 事件时间线"])
                for event in self.log_analysis["timeline"]:
                    lines.append(f"- [{event.get('time', 'N/A')}] {event.get('event', '')} ({event.get('severity', '')})")

            lines.append("")

        # 根因分析部分
        if self.root_cause:
            lines.extend([
                "## 🔍 根因分析",
                "",
                f"**根本原因**: {self.root_cause.get('root_cause', 'N/A')}",
                f"**故障类别**: {self.root_cause.get('root_cause_category', 'N/A')}",
                f"**置信度**: {self.root_cause.get('confidence', 0) * 100:.0f}%",
                f"**严重程度**: {self.root_cause.get('severity', 'N/A')}",
                f"**影响范围**: {self.root_cause.get('impact_scope', 'N/A')}",
                "",
            ])

            if self.root_cause.get("direct_causes"):
                lines.append("### 直接原因")
                for cause in self.root_cause["direct_causes"]:
                    lines.append(f"- **{cause.get('cause', '')}**: {cause.get('evidence', '')}")

            if self.root_cause.get("analysis_chain"):
                lines.extend(["", "### 分析链路"])
                for step in self.root_cause["analysis_chain"]:
                    lines.append(f"1. {step}")

            lines.append("")

        # 修复建议部分
        if self.fix_suggestion:
            lines.extend([
                "## 🛠️ 修复建议",
                "",
            ])

            # 立即止血
            immediate = self.fix_suggestion.get("immediate_fix", {})
            if immediate:
                lines.extend([
                    "### 🚨 立即止血方案",
                    "",
                    f"**描述**: {immediate.get('description', 'N/A')}",
                    f"**预计耗时**: {immediate.get('estimated_time', 'N/A')}",
                    f"**风险等级**: {immediate.get('risk_level', 'N/A')}",
                    "",
                    "**操作步骤**:",
                ])
                for step in immediate.get("steps", []):
                    lines.append(f"{step.get('step', '')}. **{step.get('action', '')}**")
                    if step.get("command"):
                        lines.append(f"   ```bash")
                        lines.append(f"   {step['command']}")
                        lines.append(f"   ```")
                    if step.get("expected_result"):
                        lines.append(f"   预期结果: {step['expected_result']}")
                lines.append("")

            # 根本解决
            root_fix = self.fix_suggestion.get("root_fix", {})
            if root_fix:
                lines.extend([
                    "### 🎯 根本解决方案",
                    "",
                    f"**描述**: {root_fix.get('description', 'N/A')}",
                    f"**预计耗时**: {root_fix.get('estimated_time', 'N/A')}",
                    f"**需要停机**: {'是' if root_fix.get('requires_downtime') else '否'}",
                    "",
                    "**操作步骤**:",
                ])
                for step in root_fix.get("steps", []):
                    lines.append(f"{step.get('step', '')}. **{step.get('action', '')}**")
                    if step.get("command"):
                        lines.append(f"   ```bash")
                        lines.append(f"   {step['command']}")
                        lines.append(f"   ```")
                lines.append("")

            # 验证方法
            verification = self.fix_suggestion.get("verification", {})
            if verification:
                lines.extend([
                    "### ✅ 验证方法",
                    "",
                ])
                for step in verification.get("steps", []):
                    lines.append(f"- {step}")
                if verification.get("success_criteria"):
                    lines.append(f"\n**成功标准**: {verification['success_criteria']}")
                lines.append("")

            # 回滚方案
            rollback = self.fix_suggestion.get("rollback", {})
            if rollback and rollback.get("steps"):
                lines.extend([
                    "### ⏪ 回滚方案",
                    "",
                    f"**描述**: {rollback.get('description', 'N/A')}",
                    "",
                ])
                for step in rollback.get("steps", []):
                    lines.append(f"- {step}")
                lines.append("")

            # 预防措施
            prevention = self.fix_suggestion.get("prevention", {})
            if prevention:
                lines.extend([
                    "### 🛡️ 预防措施",
                    "",
                ])
                if prevention.get("monitoring"):
                    lines.append("**需要添加的监控**:")
                    for item in prevention["monitoring"]:
                        lines.append(f"- {item}")
                if prevention.get("alerts"):
                    lines.append("\n**需要配置的告警**:")
                    for item in prevention["alerts"]:
                        lines.append(f"- {item}")
                if prevention.get("best_practices"):
                    lines.append("\n**最佳实践**:")
                    for item in prevention["best_practices"]:
                        lines.append(f"- {item}")

        if self.error:
            lines.extend([
                "",
                "## ❌ 错误信息",
                "",
                self.error,
            ])

        return "\n".join(lines)

    def _generate_text_report(self) -> str:
        """生成纯文本报告"""
        lines = [
            "=" * 60,
            "运维故障诊断报告",
            "=" * 60,
            f"诊断时间: {self.timestamp}",
            f"分析日志数: {self.logs_count}",
            f"诊断状态: {'成功' if self.success else '失败'}",
            "",
        ]

        if self.log_analysis:
            lines.extend([
                "-" * 40,
                "日志分析",
                "-" * 40,
                f"错误摘要: {self.log_analysis.get('error_summary', 'N/A')}",
                f"错误类型: {', '.join(self.log_analysis.get('error_types', []))}",
                "",
            ])

        if self.root_cause:
            lines.extend([
                "-" * 40,
                "根因分析",
                "-" * 40,
                f"根本原因: {self.root_cause.get('root_cause', 'N/A')}",
                f"置信度: {self.root_cause.get('confidence', 0) * 100:.0f}%",
                f"严重程度: {self.root_cause.get('severity', 'N/A')}",
                "",
            ])

        if self.fix_suggestion:
            immediate = self.fix_suggestion.get("immediate_fix", {})
            lines.extend([
                "-" * 40,
                "修复建议",
                "-" * 40,
                f"立即止血: {immediate.get('description', 'N/A')}",
                "",
            ])

        return "\n".join(lines)


class Orchestrator:
    """Agent编排器"""

    def __init__(self, config: AppConfig):
        self.config = config
        self.logger = setup_logger("Orchestrator", config.log_level)

        # 初始化组件
        self.knowledge_base = KnowledgeBase(config)
        self.log_analysis_agent = LogAnalysisAgent(config)
        self.root_cause_agent = RootCauseAgent(config, self.knowledge_base)
        self.fix_suggestion_agent = FixSuggestionAgent(config)

    def init_knowledge_base(self, fault_library_path: Optional[str] = None):
        """初始化知识库"""
        try:
            if fault_library_path:
                self.knowledge_base.load_fault_library(fault_library_path)
                self.logger.info("知识库初始化完成")
            else:
                self.logger.info("未指定故障库文件，跳过知识库初始化")
        except Exception as e:
            self.logger.warning(f"知识库初始化失败: {e}")

    def diagnose(
        self,
        source_type: str = "local",
        file_pattern: str = "*.log",
        hours: int = 24,
        keywords: Optional[list[str]] = None,
        levels: Optional[list[str]] = None,
        **kwargs
    ) -> DiagnosisResult:
        """执行完整诊断流程"""
        self.logger.info(f"开始诊断 (数据源: {source_type})")
        result = DiagnosisResult()

        try:
            # 步骤1: 采集日志
            self.logger.info("步骤1: 采集日志...")
            collector = create_collector(source_type, self.config)

            if not collector.is_available():
                raise Exception(f"日志采集器不可用: {source_type}")

            logs = collector.collect(
                file_pattern=file_pattern,
                hours=hours,
                keywords=keywords,
                levels=levels,
                **kwargs
            )
            result.logs_count = len(logs)
            self.logger.info(f"采集到 {len(logs)} 条日志")

            if not logs:
                result.success = True
                result.error = "未采集到符合条件的日志"
                return result

            # 步骤2: 日志分析
            self.logger.info("步骤2: 日志分析...")
            analysis_result = self.log_analysis_agent.execute(logs=logs)
            if analysis_result.success:
                result.log_analysis = analysis_result.data
            else:
                self.logger.warning(f"日志分析失败: {analysis_result.error}")

            # 步骤3: 根因定位
            self.logger.info("步骤3: 根因定位...")
            if result.log_analysis:
                root_cause_result = self.root_cause_agent.execute(
                    log_analysis=result.log_analysis
                )
                if root_cause_result.success:
                    result.root_cause = root_cause_result.data
                else:
                    self.logger.warning(f"根因分析失败: {root_cause_result.error}")

            # 步骤4: 修复建议
            self.logger.info("步骤4: 生成修复建议...")
            if result.root_cause:
                fix_result = self.fix_suggestion_agent.execute(
                    root_cause_analysis=result.root_cause,
                    log_analysis=result.log_analysis
                )
                if fix_result.success:
                    result.fix_suggestion = fix_result.data
                else:
                    self.logger.warning(f"修复建议生成失败: {fix_result.error}")

            self.logger.info("诊断完成")
            result.success = True

        except Exception as e:
            self.logger.error(f"诊断失败: {e}")
            result.success = False
            result.error = str(e)

        return result

    def diagnose_from_logs(
        self,
        logs: list[LogEntry],
        context: Optional[str] = None
    ) -> DiagnosisResult:
        """直接从日志对象诊断"""
        self.logger.info(f"开始诊断 ({len(logs)} 条日志)")
        result = DiagnosisResult(logs_count=len(logs))

        try:
            # 步骤1: 日志分析
            analysis_result = self.log_analysis_agent.execute(logs=logs, context=context)
            if analysis_result.success:
                result.log_analysis = analysis_result.data

            # 步骤2: 根因定位
            if result.log_analysis:
                root_cause_result = self.root_cause_agent.execute(
                    log_analysis=result.log_analysis
                )
                if root_cause_result.success:
                    result.root_cause = root_cause_result.data

            # 步骤3: 修复建议
            if result.root_cause:
                fix_result = self.fix_suggestion_agent.execute(
                    root_cause_analysis=result.root_cause,
                    log_analysis=result.log_analysis
                )
                if fix_result.success:
                    result.fix_suggestion = fix_result.data

            result.success = True

        except Exception as e:
            result.success = False
            result.error = str(e)

        return result
