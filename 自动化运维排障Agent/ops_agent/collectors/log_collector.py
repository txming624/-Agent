"""
日志采集模块
支持本地日志文件和Elasticsearch两种数据源
"""

import re
import glob
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

from ..config import AppConfig


@dataclass
class LogEntry:
    """日志条目"""
    timestamp: Optional[datetime] = None
    level: str = "INFO"
    source: str = ""
    message: str = ""
    raw: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "level": self.level,
            "source": self.source,
            "message": self.message,
            "raw": self.raw,
            "metadata": self.metadata
        }

    def __str__(self) -> str:
        ts = self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else "N/A"
        return f"[{ts}] [{self.level}] [{self.source}] {self.message[:200]}"


class LogCollector(ABC):
    """日志采集器基类"""

    @abstractmethod
    def collect(self, **kwargs) -> list[LogEntry]:
        """采集日志"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查采集器是否可用"""
        pass


class LocalFileCollector(LogCollector):
    """本地日志文件采集器"""

    # 常见日志格式正则
    LOG_PATTERNS = {
        "standard": re.compile(
            r"(?P<timestamp>\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)\s*"
            r"(?:\[(?P<level>\w+)\]|(?P<level2>\w+))\s*"
            r"(?:\[(?P<source>[^\]]+)\])?\s*"
            r"(?P<message>.*)",
            re.DOTALL
        ),
        "nginx": re.compile(
            r"(?P<ip>[\d.]+)\s+-\s+\S+\s+\[(?P<timestamp>[^\]]+)\]\s+"
            r"\"(?P<request>[^\"]+)\"\s+(?P<status>\d+)\s+(?P<size>\d+)"
        ),
        "simple": re.compile(r"(?P<message>.*)", re.DOTALL)
    }

    def __init__(self, config: AppConfig):
        self.config = config
        self.log_dir = Path(config.log_dir)

    def is_available(self) -> bool:
        return self.log_dir.exists()

    def collect(
        self,
        file_pattern: str = "*.log",
        hours: int = 24,
        max_lines: int = 10000,
        keywords: Optional[list[str]] = None,
        levels: Optional[list[str]] = None,
        **kwargs
    ) -> list[LogEntry]:
        """采集本地日志文件"""
        entries = []
        cutoff_time = datetime.now() - timedelta(hours=hours)

        log_files = glob.glob(str(self.log_dir / file_pattern))
        if not log_files:
            log_files = glob.glob(str(self.log_dir / "**" / "*.log"), recursive=True)

        for file_path in log_files:
            try:
                file_entries = self._parse_file(file_path, cutoff_time, max_lines)
                
                # 关键词过滤
                if keywords:
                    file_entries = [
                        e for e in file_entries
                        if any(kw.lower() in e.message.lower() for kw in keywords)
                    ]
                
                # 级别过滤
                if levels:
                    levels_upper = [l.upper() for l in levels]
                    file_entries = [
                        e for e in file_entries
                        if e.level.upper() in levels_upper
                    ]
                
                entries.extend(file_entries)
            except Exception as e:
                print(f"解析文件 {file_path} 失败: {e}")

        # 按时间排序
        entries.sort(key=lambda x: x.timestamp or datetime.min)
        return entries[:max_lines]

    def _parse_file(
        self, file_path: str, cutoff_time: datetime, max_lines: int
    ) -> list[LogEntry]:
        """解析单个日志文件"""
        entries = []
        path = Path(file_path)

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    break

                line = line.strip()
                if not line:
                    continue

                entry = self._parse_line(line, path.name)
                if entry and entry.timestamp and entry.timestamp >= cutoff_time:
                    entries.append(entry)
                elif not entry.timestamp:
                    entries.append(entry)

        return entries

    def _parse_line(self, line: str, source: str) -> LogEntry:
        """解析单行日志"""
        for pattern_name, pattern in self.LOG_PATTERNS.items():
            match = pattern.match(line)
            if match:
                groups = match.groupdict()
                
                timestamp = self._parse_timestamp(groups.get("timestamp", ""))
                level = (
                    groups.get("level", "") or 
                    groups.get("level2", "") or 
                    self._detect_level(line)
                ).upper() or "INFO"
                
                return LogEntry(
                    timestamp=timestamp,
                    level=level,
                    source=source,
                    message=groups.get("message", line),
                    raw=line
                )

        return LogEntry(
            level=self._detect_level(line),
            source=source,
            message=line,
            raw=line
        )

    def _parse_timestamp(self, ts_str: str) -> Optional[datetime]:
        """解析时间戳"""
        if not ts_str:
            return None
        
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S,%f",
            "%Y-%m-%d %H:%M:%S.%f",
            "%d/%b/%Y:%H:%M:%S",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(ts_str.strip(), fmt)
            except ValueError:
                continue
        return None

    def _detect_level(self, line: str) -> str:
        """检测日志级别"""
        line_upper = line.upper()
        for level in ["CRITICAL", "FATAL", "ERROR", "WARN", "WARNING", "INFO", "DEBUG", "TRACE"]:
            if level in line_upper:
                return level
        return "INFO"


class ElasticsearchCollector(LogCollector):
    """Elasticsearch日志采集器"""

    def __init__(self, config: AppConfig):
        self.config = config
        self._client = None

    def _get_client(self):
        """获取ES客户端"""
        if self._client is None:
            try:
                from elasticsearch import Elasticsearch
                
                es_config = self.config.elasticsearch
                hosts = es_config.hosts.split(",")
                
                kwargs = {"hosts": hosts}
                if es_config.username and es_config.password:
                    kwargs["basic_auth"] = (es_config.username, es_config.password)
                kwargs["verify_certs"] = es_config.verify_certs
                
                self._client = Elasticsearch(**kwargs)
            except ImportError:
                raise ImportError("请安装 elasticsearch: pip install elasticsearch")
        return self._client

    def is_available(self) -> bool:
        try:
            client = self._get_client()
            return client.ping()
        except Exception:
            return False

    def collect(
        self,
        index_pattern: Optional[str] = None,
        hours: int = 24,
        max_size: int = 10000,
        keywords: Optional[list[str]] = None,
        levels: Optional[list[str]] = None,
        query_string: Optional[str] = None,
        **kwargs
    ) -> list[LogEntry]:
        """从ES采集日志"""
        client = self._get_client()
        index = index_pattern or self.config.elasticsearch.index_pattern

        # 构建查询
        must_clauses = []
        
        # 时间范围
        must_clauses.append({
            "range": {
                "@timestamp": {
                    "gte": f"now-{hours}h",
                    "lte": "now"
                }
            }
        })

        # 关键词查询
        if keywords:
            should_clauses = [{"match": {"message": kw}} for kw in keywords]
            must_clauses.append({"bool": {"should": should_clauses, "minimum_should_match": 1}})

        # 日志级别
        if levels:
            must_clauses.append({"terms": {"level": [l.upper() for l in levels]}})

        # 自定义查询字符串
        if query_string:
            must_clauses.append({"query_string": {"query": query_string}})

        query = {
            "bool": {
                "must": must_clauses
            }
        } if must_clauses else {"match_all": {}}

        try:
            response = client.search(
                index=index,
                query=query,
                size=max_size,
                sort=[{"@timestamp": {"order": "asc"}}]
            )

            entries = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                entry = LogEntry(
                    timestamp=self._parse_es_timestamp(source.get("@timestamp")),
                    level=source.get("level", source.get("severity", "INFO")).upper(),
                    source=source.get("service", source.get("host", {}).get("name", "")),
                    message=source.get("message", ""),
                    raw=str(source),
                    metadata={"_id": hit["_id"], "_index": hit["_index"]}
                )
                entries.append(entry)

            return entries

        except Exception as e:
            print(f"ES查询失败: {e}")
            return []

    def _parse_es_timestamp(self, ts) -> Optional[datetime]:
        """解析ES时间戳"""
        if isinstance(ts, str):
            for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"]:
                try:
                    return datetime.strptime(ts, fmt)
                except ValueError:
                    continue
        return None


def create_collector(source_type: str, config: AppConfig) -> LogCollector:
    """工厂函数：创建日志采集器"""
    collectors = {
        "local": LocalFileCollector,
        "elasticsearch": ElasticsearchCollector,
        "es": ElasticsearchCollector,
    }
    
    collector_class = collectors.get(source_type.lower())
    if not collector_class:
        raise ValueError(f"不支持的日志源类型: {source_type}，可选: {list(collectors.keys())}")
    
    return collector_class(config)
