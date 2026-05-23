"""
运维排障Agent - 配置管理模块
支持环境变量和.env文件加载
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class LLMConfig:
    """LLM配置"""
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o"))
    temperature: float = field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.1")))
    max_tokens: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "4096")))


@dataclass
class ElasticsearchConfig:
    """Elasticsearch配置"""
    hosts: str = field(default_factory=lambda: os.getenv("ES_HOSTS", "localhost:9200"))
    username: Optional[str] = field(default_factory=lambda: os.getenv("ES_USERNAME"))
    password: Optional[str] = field(default_factory=lambda: os.getenv("ES_PASSWORD"))
    index_pattern: str = field(default_factory=lambda: os.getenv("ES_INDEX_PATTERN", "logs-*"))
    verify_certs: bool = field(default_factory=lambda: os.getenv("ES_VERIFY_CERTS", "false").lower() == "true")


@dataclass
class RAGConfig:
    """RAG配置"""
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
    embedding_base_url: str = field(default_factory=lambda: os.getenv("EMBEDDING_BASE_URL", ""))
    vector_db_path: str = field(default_factory=lambda: os.getenv("VECTOR_DB_PATH", "./data/chroma_db"))
    collection_name: str = field(default_factory=lambda: os.getenv("COLLECTION_NAME", "fault_library"))
    top_k: int = field(default_factory=lambda: int(os.getenv("RAG_TOP_K", "3")))


@dataclass
class AppConfig:
    """应用配置"""
    llm: LLMConfig = field(default_factory=LLMConfig)
    elasticsearch: ElasticsearchConfig = field(default_factory=ElasticsearchConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_dir: str = field(default_factory=lambda: os.getenv("LOG_DIR", "./logs"))
    data_dir: str = field(default_factory=lambda: os.getenv("DATA_DIR", "./data"))
    
    def validate(self) -> list[str]:
        """验证配置，返回错误列表"""
        errors = []
        if not self.llm.api_key:
            errors.append("LLM_API_KEY 未配置")
        if not self.llm.base_url:
            errors.append("LLM_BASE_URL 未配置")
        return errors


def load_config() -> AppConfig:
    """加载配置"""
    config = AppConfig()
    errors = config.validate()
    if errors:
        print("⚠️  配置警告:")
        for err in errors:
            print(f"   - {err}")
        print("   请检查 .env 文件或环境变量")
    return config
