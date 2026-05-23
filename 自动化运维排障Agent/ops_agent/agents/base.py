"""
Agent基类
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass, field

from ..config import AppConfig
from ..utils import setup_logger


@dataclass
class AgentResult:
    """Agent执行结果"""
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "summary": self.summary,
            "error": self.error,
        }


class BaseAgent(ABC):
    """Agent基类"""

    def __init__(self, config: AppConfig):
        self.config = config
        self.logger = setup_logger(self.__class__.__name__, config.log_level)
        self._client = None

    def _get_llm_client(self):
        """获取LLM客户端"""
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.config.llm.api_key,
                base_url=self.config.llm.base_url,
            )
        return self._client

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """调用LLM"""
        client = self._get_llm_client()

        response = client.chat.completions.create(
            model=self.config.llm.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.config.llm.temperature,
            max_tokens=self.config.llm.max_tokens,
        )

        return response.choices[0].message.content or ""

    @abstractmethod
    def execute(self, **kwargs) -> AgentResult:
        """执行Agent任务"""
        pass
