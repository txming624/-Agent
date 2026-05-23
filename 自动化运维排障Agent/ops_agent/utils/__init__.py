"""
工具函数模块
"""

import logging
from datetime import datetime


def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """配置日志记录器"""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def format_timestamp(dt: datetime) -> str:
    """格式化时间戳"""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def truncate_text(text: str, max_length: int = 500) -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def extract_error_patterns(logs: list[str]) -> dict[str, int]:
    """提取错误模式"""
    patterns = {
        "timeout": r"timeout|timed?\s*out",
        "connection_error": r"connection\s*(refused|reset|error|failed)",
        "oom": r"out\s*of\s*memory|oom|heap\s*space",
        "permission": r"permission\s*denied|access\s*denied|forbidden",
        "disk_full": r"no\s*space\s*left|disk\s*full",
        "certificate": r"certificate|ssl|tls",
        "dns": r"dns|resolve|name\s*resolution",
        "auth": r"auth|unauthorized|401|403",
    }

    import re
    results = {}
    combined_logs = " ".join(logs).lower()

    for pattern_name, regex in patterns.items():
        matches = re.findall(regex, combined_logs, re.IGNORECASE)
        if matches:
            results[pattern_name] = len(matches)

    return results


def generate_report(
    title: str,
    sections: dict[str, str],
    format: str = "markdown"
) -> str:
    """生成报告"""
    if format == "markdown":
        lines = [f"# {title}", ""]
        for section_name, content in sections.items():
            lines.append(f"## {section_name}")
            lines.append("")
            lines.append(content)
            lines.append("")
        return "\n".join(lines)
    else:
        lines = [f"=== {title} ===", ""]
        for section_name, content in sections.items():
            lines.append(f"--- {section_name} ---")
            lines.append(content)
            lines.append("")
        return "\n".join(lines)
