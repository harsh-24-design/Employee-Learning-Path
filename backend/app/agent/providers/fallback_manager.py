import time
import logging
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.agent.providers.base import (
    BaseLLMProvider,
    LLMMessage,
    LLMResponse,
    ErrorCategory,
    ProviderException,
    redact_secrets
)
from app.agent.providers.gemini_provider import GeminiProvider
from app.agent.providers.openai_provider import OpenAIProvider
from app.agent.providers.grok_provider import GrokProvider

logger = logging.getLogger("learning_agent.fallback_manager")

class LLMFallbackManager:
    """
    Orchestrates multi-provider LLM execution with automatic fallback.
    Supported providers: Gemini, OpenAI, xAI Grok.
    Adheres strictly to configured provider priority (LLM_PRIMARY_PROVIDER, LLM_FALLBACK_ORDER),
    enforces bounded retries, isolates credentials, and records observability metrics.
    """

    def __init__(self):
        self.providers: Dict[str, BaseLLMProvider] = {
            "gemini": GeminiProvider(),
            "openai": OpenAIProvider(),
            "grok": GrokProvider()
        }
        self.execution_audit_log: List[Dict[str, Any]] = []
        self._max_audit_logs = 100

    def get_provider(self, name: str) -> Optional[BaseLLMProvider]:
        return self.providers.get(name.lower())

    def _record_audit(
        self,
        provider: str,
        model: str,
        duration: float,
        status: str,
        failure_category: Optional[str] = None,
        fallback_occurred: bool = False
    ):
        entry = {
            "timestamp": time.time(),
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "provider": provider,
            "model": model,
            "duration_sec": round(duration, 3),
            "status": status,
            "failure_category": failure_category,
            "fallback_occurred": fallback_occurred
        }
        self.execution_audit_log.append(entry)
        if len(self.execution_audit_log) > self._max_audit_logs:
            self.execution_audit_log.pop(0)

        log_level = logging.INFO if status == "SUCCESS" else logging.WARNING
        logger.log(
            log_level,
            f"LLM Provider [{provider}] model=[{model}] duration=[{duration:.2f}s] status=[{status}] "
            f"fallback=[{fallback_occurred}] failure_category=[{failure_category}]"
        )

    def generate(
        self,
        messages: List[LLMMessage],
        system_prompt: str,
        temperature: float = 0.7,
        timeout: Optional[float] = None
    ) -> LLMResponse:
        """
        Executes completion across configured providers in priority order.
        Falls over automatically on retryable, quota, network, or server failures.
        """
        order = settings.get_provider_order()
        req_timeout = timeout or settings.LLM_REQUEST_TIMEOUT or 30.0

        # Check if at least one provider has credentials
        configured_providers = [p_name for p_name in order if self.providers.get(p_name) and self.providers[p_name].is_configured()]
        if not configured_providers:
            # Check what primary provider was requested to provide clear guidance
            primary = (settings.LLM_PRIMARY_PROVIDER or "gemini").lower()
            env_var = "GEMINI_API_KEY" if primary == "gemini" else ("OPENAI_API_KEY" if primary == "openai" else "XAI_API_KEY")
            raise ProviderException(
                message=(
                    f"AI Advisor Configuration Notice: No LLM provider is currently configured. "
                    f"Please configure '{env_var}' in your backend/.env file to enable live AI responses."
                ),
                category=ErrorCategory.CONFIG_MISSING,
                is_retryable=False,
                provider="none"
            )

        attempt_errors: List[Dict[str, Any]] = []
        fallback_triggered = False

        for idx, provider_name in enumerate(order):
            provider = self.providers.get(provider_name)
            if not provider:
                continue

            if not provider.is_configured():
                logger.debug(f"Skipping unconfigured provider: {provider_name}")
                continue

            is_fallback_attempt = idx > 0 or fallback_triggered
            model_target = getattr(provider, "_cached_model", "") or provider.name
            start_time = time.time()

            max_retries = 2
            current_attempt = 0
            while current_attempt < max_retries:
                current_attempt += 1
                try:
                    res = provider.generate(
                        messages=messages,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        timeout=req_timeout
                    )
                    duration = time.time() - start_time
                    self._record_audit(
                        provider=provider_name,
                        model=res.model,
                        duration=duration,
                        status="SUCCESS",
                        fallback_occurred=is_fallback_attempt
                    )
                    return res

                except ProviderException as pe:
                    duration = time.time() - start_time
                    self._record_audit(
                        provider=provider_name,
                        model=model_target,
                        duration=duration,
                        status="FAILED",
                        failure_category=pe.category.value if hasattr(pe.category, "value") else str(pe.category),
                        fallback_occurred=is_fallback_attempt
                    )

                    attempt_errors.append({
                        "provider": provider_name,
                        "category": pe.category,
                        "message": pe.message,
                        "is_retryable": pe.is_retryable
                    })

                    # If permanent error (invalid key, unsupported model), DO NOT retry this provider
                    if not pe.is_retryable:
                        logger.warning(f"Provider [{provider_name}] permanent error ({pe.category}). Advancing to next backup provider.")
                        fallback_triggered = True
                        break

                    # If transient error and have retry quota left
                    if current_attempt < max_retries:
                        backoff = 0.5 * (2 ** (current_attempt - 1))
                        logger.info(f"Transient error on [{provider_name}] ({pe.category}). Retrying in {backoff}s...")
                        time.sleep(backoff)
                        continue

                    # Retries exhausted for this provider, fall over to next
                    fallback_triggered = True
                    break

                except Exception as unk_e:
                    duration = time.time() - start_time
                    clean_msg = redact_secrets(str(unk_e))
                    self._record_audit(
                        provider=provider_name,
                        model=model_target,
                        duration=duration,
                        status="FAILED",
                        failure_category="unknown_error",
                        fallback_occurred=is_fallback_attempt
                    )
                    attempt_errors.append({
                        "provider": provider_name,
                        "category": ErrorCategory.UNKNOWN,
                        "message": clean_msg,
                        "is_retryable": False
                    })
                    fallback_triggered = True
                    break

        # If we reached here, all eligible providers failed
        failed_summary = ", ".join([f"{e['provider']} ({e['category']})" for e in attempt_errors])
        first_error_msg = attempt_errors[0]["message"] if attempt_errors else "All configured providers failed."

        raise ProviderException(
            message=(
                f"AI Service Error: All configured LLM providers failed [{failed_summary}]. "
                f"Details: {first_error_msg}"
            ),
            category=ErrorCategory.SERVER_ERROR_5XX,
            is_retryable=False,
            provider="fallback_manager"
        )

    def get_provider_statuses(self) -> Dict[str, Any]:
        """
        Returns safe debugging status across all providers and recent executions.
        Zero credentials or secrets are exposed.
        """
        statuses = []
        for name in settings.get_provider_order():
            provider = self.providers.get(name)
            if provider:
                statuses.append(provider.get_status())

        recent_audits = self.execution_audit_log[-10:] if self.execution_audit_log else []

        return {
            "primary_provider": settings.LLM_PRIMARY_PROVIDER,
            "fallback_order": settings.get_provider_order(),
            "timeout_seconds": settings.LLM_REQUEST_TIMEOUT,
            "providers": statuses,
            "recent_activity": recent_audits
        }

# Global singleton fallback manager
fallback_manager = LLMFallbackManager()
