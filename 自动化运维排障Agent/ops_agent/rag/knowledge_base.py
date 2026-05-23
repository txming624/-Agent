"""
RAG知识库模块
基于ChromaDB的向量检索，接入历史故障库
"""

import json
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

from ..config import AppConfig


@dataclass
class FaultCase:
    """故障案例"""
    id: str
    title: str
    category: str
    symptoms: list[str]
    root_cause: str
    solution: str
    severity: str = "medium"
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_document(self) -> str:
        """转换为文档文本（用于向量化）"""
        parts = [
            f"故障标题: {self.title}",
            f"故障分类: {self.category}",
            f"严重程度: {self.severity}",
            f"故障症状: {'; '.join(self.symptoms)}",
            f"根本原因: {self.root_cause}",
            f"解决方案: {self.solution}",
        ]
        if self.tags:
            parts.append(f"标签: {', '.join(self.tags)}")
        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "symptoms": self.symptoms,
            "root_cause": self.root_cause,
            "solution": self.solution,
            "severity": self.severity,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FaultCase":
        return cls(**data)


class KnowledgeBase:
    """知识库管理"""

    def __init__(self, config: AppConfig):
        self.config = config
        self._collection = None
        self._embedding_fn = None
        self._initialized = False

    def _init_chroma(self):
        """初始化ChromaDB"""
        if self._initialized:
            return

        try:
            import chromadb
            from chromadb.config import Settings

            persist_dir = self.config.rag.vector_db_path
            Path(persist_dir).mkdir(parents=True, exist_ok=True)

            client = chromadb.PersistentClient(
                path=persist_dir,
                settings=Settings(anonymized_telemetry=False)
            )

            self._collection = client.get_or_create_collection(
                name=self.config.rag.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            self._initialized = True

        except ImportError:
            raise ImportError("请安装 chromadb: pip install chromadb")

    def _get_embedding(self, text: str) -> list[float]:
        """获取文本的向量嵌入"""
        try:
            from openai import OpenAI

            embedding_url = self.config.rag.embedding_base_url or self.config.llm.base_url
            client = OpenAI(
                api_key=self.config.llm.api_key,
                base_url=embedding_url
            )

            response = client.embeddings.create(
                model=self.config.rag.embedding_model,
                input=text
            )
            return response.data[0].embedding

        except ImportError:
            raise ImportError("请安装 openai: pip install openai")

    def load_fault_library(self, file_path: str):
        """加载故障库到向量数据库"""
        self._init_chroma()

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        faults = [FaultCase.from_dict(item) for item in data]
        self.add_faults(faults)
        print(f"✅ 已加载 {len(faults)} 条故障案例到知识库")

    def add_faults(self, faults: list[FaultCase]):
        """添加故障案例"""
        self._init_chroma()

        documents = []
        metadatas = []
        ids = []

        for fault in faults:
            doc = fault.to_document()
            documents.append(doc)
            metadatas.append({
                "id": fault.id,
                "title": fault.title,
                "category": fault.category,
                "severity": fault.severity,
                "tags": ",".join(fault.tags),
            })
            ids.append(fault.id)

        # 批量获取嵌入并添加
        embeddings = [self._get_embedding(doc) for doc in documents]

        self._collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )

    def search(self, query: str, top_k: Optional[int] = None) -> list[dict]:
        """搜索相关故障案例"""
        self._init_chroma()

        k = top_k or self.config.rag.top_k
        query_embedding = self._get_embedding(query)

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            include=["documents", "metadatas", "distances"]
        )

        matches = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                matches.append({
                    "content": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "score": 1 - results["distances"][0][i] if results["distances"] else 0,
                })

        return matches

    def get_stats(self) -> dict:
        """获取知识库统计信息"""
        self._init_chroma()
        return {
            "total_documents": self._collection.count(),
            "collection_name": self.config.rag.collection_name,
        }
