"""LLM Registry - 多供应商支持与 Failover 机制"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import os
from typing import Any, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from structlog import get_logger

from app.agent.tools.base import RiskLevel

logger = get_logger()


# 全局实例声明（必须在使用前）
_llm_registry: "LLMRegistry | None" = None


class ProviderStatus(str, Enum):
    """供应商状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass
class ProviderConfig:
    """LLM 供应商配置"""
    name: str
    endpoint: str
    api_key: str
    model: str
    priority: int = 1
    max_tokens: int = 4096
    temperature: float = 0.7
    status: ProviderStatus = ProviderStatus.HEALTHY
    error_count: int = 0
    last_error: str | None = None


class IntentClassification(BaseModel):
    """意图分类结果"""
    intent: str  # query, diagnosis, suggestion, action, unknown
    entity_type: str | None = None  # spark, yunikorn, k8s, cluster
    confidence: float = 0.0
    keywords: list[str] = field(default_factory=list)


class PlanStep(BaseModel):
    """规划步骤"""
    step_id: int
    tool: str
    args: dict[str, Any]
    dependencies: list[int] = field(default_factory=list)
    description: str = ""
    risk_level: RiskLevel = RiskLevel.SAFE


class PlanOutput(BaseModel):
    """规划输出"""
    steps: list[PlanStep]
    reasoning: str = ""


class LLMRegistry:
    """LLM 注册表 - 多供应商 Failover"""

    def __init__(self) -> None:
        self.providers: list[ProviderConfig] = self._load_providers()
        self._llm_cache: dict[str, BaseChatModel] = {}

    def _load_providers(self) -> list[ProviderConfig]:
        """从环境变量加载供应商配置"""
        providers = []

        # Primary provider
        primary_endpoint = os.getenv("LLM_PRIMARY_ENDPOINT", "")
        primary_key = os.getenv("LLM_PRIMARY_API_KEY", "")
        primary_model = os.getenv("LLM_PRIMARY_MODEL", "gpt-4")

        if primary_endpoint and primary_key:
            providers.append(
                ProviderConfig(
                    name="primary",
                    endpoint=primary_endpoint,
                    api_key=primary_key,
                    model=primary_model,
                    priority=1,
                )
            )

        # Fallback provider
        fallback_endpoint = os.getenv("LLM_FALLBACK_ENDPOINT", "")
        fallback_key = os.getenv("LLM_FALLBACK_API_KEY", "")
        fallback_model = os.getenv("LLM_FALLBACK_MODEL", "gpt-3.5-turbo")

        if fallback_endpoint and fallback_key:
            providers.append(
                ProviderConfig(
                    name="fallback",
                    endpoint=fallback_endpoint,
                    api_key=fallback_key,
                    model=fallback_model,
                    priority=2,
                )
            )

        # 按优先级排序
        providers.sort(key=lambda p: p.priority)

        if not providers:
            logger.warning("no_llm_providers_configured")

        return providers

    def _get_llm(self, provider: ProviderConfig) -> BaseChatModel:
        """获取 LLM 实例（带缓存）"""
        cache_key = f"{provider.name}:{provider.model}"

        if cache_key not in self._llm_cache:
            self._llm_cache[cache_key] = ChatOpenAI(
                base_url=provider.endpoint,
                api_key=provider.api_key,
                model=provider.model,
                max_tokens=provider.max_tokens,
                temperature=provider.temperature,
            )

        return self._llm_cache[cache_key]

    def _get_healthy_provider(self) -> ProviderConfig | None:
        """获取健康的供应商"""
        for provider in self.providers:
            if provider.status != ProviderStatus.FAILED:
                return provider
        return None

    def _mark_provider_failed(self, provider: ProviderConfig, error: str) -> None:
        """标记供应商失败"""
        provider.error_count += 1
        provider.last_error = error

        if provider.error_count >= 3:
            provider.status = ProviderStatus.FAILED
            logger.error(
                "provider_marked_failed",
                provider=provider.name,
                error_count=provider.error_count,
                error=error,
            )

    async def invoke(self, prompt: str) -> str:
        """调用 LLM（带 Failover）"""
        for provider in self.providers:
            if provider.status == ProviderStatus.FAILED:
                continue

            try:
                llm = self._get_llm(provider)
                response = await asyncio.to_thread(llm.invoke, prompt)
                logger.info(
                    "llm_response_success",
                    provider=provider.name,
                    model=provider.model,
                )
                # 重置错误计数
                provider.error_count = 0
                provider.status = ProviderStatus.HEALTHY
                return response.content if hasattr(response, "content") else str(response)

            except Exception as e:
                error_msg = str(e)
                logger.warning(
                    "llm_error",
                    provider=provider.name,
                    error=error_msg,
                )
                self._mark_provider_failed(provider, error_msg)

                # 尝试下一个供应商
                if provider != self.providers[-1]:
                    logger.info(
                        "failover_triggered",
                        from_provider=provider.name,
                        to_provider=self.providers[self.providers.index(provider) + 1].name,
                    )
                    continue

        raise RuntimeError("All LLM providers failed")

    async def classify(self, query: str) -> IntentClassification:
        """分类用户意图"""
        provider = self._get_healthy_provider()
        if not provider:
            raise RuntimeError("No healthy LLM provider available")

        llm = self._get_llm(provider)
        structured_llm = llm.with_structured_output(IntentClassification)

        classification_prompt = f"""分析以下用户查询的意图和实体类型。

用户查询：{query}

请返回：
- intent: query（查询）| diagnosis（诊断）| suggestion（建议）| action（操作）| unknown（未知）
- entity_type: spark（Spark任务）| yunikorn（YuniKorn队列）| k8s（K8s资源）| cluster（集群）| None
- confidence: 置信度 0.0-1.0
- keywords: 关键词列表"""

        try:
            result = await asyncio.to_thread(structured_llm.invoke, classification_prompt)
            return cast("IntentClassification", result)
        except Exception as e:
            logger.error("classification_failed", error=str(e))
            # 返回默认分类
            return IntentClassification(
                intent="unknown",
                entity_type=None,
                confidence=0.0,
                keywords=[],
            )

    async def plan(
        self,
        query: str,
        intent: str,
        entity_type: str | None,
        available_tools: list[str],
    ) -> PlanOutput:
        """生成执行规划"""
        provider = self._get_healthy_provider()
        if not provider:
            raise RuntimeError("No healthy LLM provider available")

        llm = self._get_llm(provider)
        structured_llm = llm.with_structured_output(PlanOutput)

        plan_prompt = f"""根据用户查询生成执行规划。

用户查询：{query}
意图类型：{intent}
实体类型：{entity_type}
可用工具：{', '.join(available_tools)}

请生成一个逐步执行计划，每个步骤包含：
- step_id: 步骤编号（1, 2, 3...）
- tool: 要使用的工具名称
- args: 工具参数（可以引用前面步骤的结果，如 #E1）
- dependencies: 依赖的步骤 ID 列表
- description: 步骤描述
- risk_level: safe | low | medium | high | critical

注意：
1. 诊断类任务通常需要先查询任务状态、再获取日志、最后分析
2. 查询类任务可以一步完成
3. 操作类任务需要考虑风险等级"""

        try:
            result = await asyncio.to_thread(structured_llm.invoke, plan_prompt)
            return cast("PlanOutput", result)
        except Exception as e:
            logger.error("planning_failed", error=str(e))
            raise

    async def analyze(self, query: str, context: dict[str, Any]) -> str:
        """分析工具执行结果"""
        provider = self._get_healthy_provider()
        if not provider:
            raise RuntimeError("No healthy LLM provider available")

        llm = self._get_llm(provider)

        analyze_prompt = f"""根据以下信息回答用户问题。

用户问题：{query}

收集到的信息：
{context}

请：
1. 分析问题的根本原因
2. 提供诊断结论
3. 给出具体的建议"""

        try:
            response = await asyncio.to_thread(llm.invoke, analyze_prompt)
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.error("analysis_failed", error=str(e))
            raise

    async def summarize(self, messages: list[dict[str, Any]]) -> str:
        """压缩会话历史为摘要"""
        provider = self._get_healthy_provider()
        if not provider:
            raise RuntimeError("No healthy LLM provider available")

        llm = self._get_llm(provider)

        summary_prompt = f"""将以下对话历史压缩为一个简洁摘要，保留关键信息。

对话历史：
{messages}

请保留：
- 用户的主要问题和目标
- 已执行的操作和结果
- 当前状态和下一步"""

        try:
            response = await asyncio.to_thread(llm.invoke, summary_prompt)
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.error("summarization_failed", error=str(e))
            raise

    async def respond(self, query: str, analysis: str) -> str:
        """生成最终响应"""
        provider = self._get_healthy_provider()
        if not provider:
            raise RuntimeError("No healthy LLM provider available")

        llm = self._get_llm(provider)

        respond_prompt = f"""根据分析结果，回答用户问题。

用户问题：{query}

分析结果：{analysis}

请用友好、专业的方式回复，包括：
1. 问题的简要描述
2. 关键发现
3. 建议的下一步"""

        try:
            response = await asyncio.to_thread(llm.invoke, respond_prompt)
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.error("response_generation_failed", error=str(e))
            raise


def get_llm_registry() -> LLMRegistry:
    """获取全局 LLM Registry 实例"""
    global _llm_registry
    if _llm_registry is None:
        _llm_registry = LLMRegistry()
    return _llm_registry
