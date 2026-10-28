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

logger = logging.getLogger("learning_agent.providers.grok")

try:
    import openai
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    openai = None
    OpenAI = None
    HAS_OPENAI = False

class GrokProvider(BaseLLMProvider):
    name = "grok"
    BASE_URL = "https://api.x.ai/v1"

    _FALLBACK_CANDIDATES = [
        "grok-3-mini",
        "grok-2-mini",
        "grok-2",
        "grok-beta"
    ]

    def __init__(self):
        self._cached_model: Optional[str] = None
        self._cached_model_time: Optional[float] = None
        self._last_error: Optional[str] = None

    def is_configured(self) -> bool:
        if not HAS_OPENAI:
            return False
        key = (settings.XAI_API_KEY or "").strip()
        return bool(key and key not in ("your_xai_api_key", "none", "replace_with_your_key"))

    def get_verified_model(self, client: Any = None, preferred_model: Optional[str] = None) -> str:
        now = time.time()
        if self._cached_model and self._cached_model_time and (now - self._cached_model_time < 3600):
            return self._cached_model

        target = preferred_model or settings.XAI_MODEL or "grok-3-mini"

        if client is not None and hasattr(client, "models") and hasattr(client.models, "list"):
            try:
                available_models = set()
                model_list = client.models.list()
                for m in model_list:
                    mid = getattr(m, "id", "")
                    if mid:
                        available_models.add(mid)

                if target in available_models:
                    self._cached_model = target
                    self._cached_model_time = now
                    return target

                for candidate in self._FALLBACK_CANDIDATES:
                    if candidate in available_models:
                        self._cached_model = candidate
                        self._cached_model_time = now
                        return candidate
            except Exception as e:
                logger.debug(f"xAI Grok model verification query failed: {e}")

        self._cached_model = target
        self._cached_model_time = now
        return target

    def _classify_error(self, e: Exception, key: str) -> tuple:
        msg = str(e)
        clean_msg = redact_secrets(msg, [key])
        err_lower = clean_msg.lower()

        if HAS_OPENAI and openai is not None:
            if isinstance(e, getattr(openai, "AuthenticationError", type(None))):
                return (
                    ErrorCategory.AUTH_INVALID_KEY,
                    False,
                    "xAI Grok API key is invalid or unauthorized."
                )
            if isinstance(e, getattr(openai, "RateLimitError", type(None))):
                return (
                    ErrorCategory.RATE_LIMIT_429,
                    True,
                    "xAI Grok rate limit or quota exceeded (429)."
                )
            if isinstance(e, getattr(openai, "NotFoundError", type(None))):
                return (
                    ErrorCategory.MODEL_UNAVAILABLE,
                    False,
                    f"xAI Grok model '{self._cached_model or settings.XAI_MODEL}' is unavailable or not found."
                )
            if isinstance(e, (getattr(openai, "APITimeoutError", type(None)), getattr(openai, "APIConnectionError", type(None)))):
                return (
                    ErrorCategory.NETWORK_TIMEOUT,
                    True,
                    "xAI Grok network connection failure or request timeout."
                )
            if isinstance(e, getattr(openai, "InternalServerError", type(None))):
                return (
                    ErrorCategory.SERVER_ERROR_5XX,
                    True,
                    "xAI Grok upstream server error (5xx)."
                )

        if any(w in err_lower for w in ["invalid_api_key", "unauthorized", "auth", "api key"]):
            return (ErrorCategory.AUTH_INVALID_KEY, False, "xAI Grok API key is invalid or unauthorized.")
        if any(w in err_lower for w in ["rate limit", "quota", "429"]):
            return (ErrorCategory.RATE_LIMIT_429, True, "xAI Grok rate limit or quota exceeded (429).")
        if any(w in err_lower for w in ["not found", "does not exist", "404", "model"]):
            return (ErrorCategory.MODEL_UNAVAILABLE, False, f"xAI Grok model '{self._cached_model or settings.XAI_MODEL}' unavailable.")
        if any(w in err_lower for w in ["timeout", "timed out", "connect"]):
            return (ErrorCategory.NETWORK_TIMEOUT, True, "xAI Grok connection failure or timeout.")
        if any(w in err_lower for w in ["500", "502", "503", "504", "internal server error"]):
            return (ErrorCategory.SERVER_ERROR_5XX, True, "xAI Grok server 5xx error.")

        return (ErrorCategory.UNKNOWN, False, f"xAI Grok error: {clean_msg}")

    def generate(
        self,
        messages: List[LLMMessage],
        system_prompt: str,
        temperature: float = 0.7,
        timeout: Optional[float] = None
    ) -> LLMResponse:
        if not HAS_OPENAI or OpenAI is None:
            raise ProviderException(
                message="openai SDK is not installed.",
                category=ErrorCategory.CONFIG_MISSING,
                is_retryable=False,
                provider=self.name
            )

        api_key = (settings.XAI_API_KEY or "").strip()
        if not api_key:
            raise ProviderException(
                message="XAI_API_KEY is not configured.",
                category=ErrorCategory.CONFIG_MISSING,
                is_retryable=False,
                provider=self.name
            )

        req_timeout = timeout or settings.LLM_REQUEST_TIMEOUT or 30.0
        start_time = time.time()

        try:
            client = OpenAI(api_key=api_key, base_url=self.BASE_URL, timeout=req_timeout)
            active_model = self.get_verified_model(client)

            formatted_messages = []
            if system_prompt:
                formatted_messages.append({"role": "system", "content": system_prompt})

            for m in messages:
                if not m.content.strip():
                    continue
                role = "assistant" if m.role == "model" else m.role
                formatted_messages.append({"role": role, "content": m.content})

            if not formatted_messages or (len(formatted_messages) == 1 and formatted_messages[0]["role"] == "system"):
                formatted_messages.append({"role": "user", "content": "Hello"})

            completion = client.chat.completions.create(
                model=active_model,
                messages=formatted_messages,
                temperature=temperature
            )

            duration = time.time() - start_time
            reply_text = completion.choices[0].message.content or ""
            self._last_error = None

            return LLMResponse(
                text=reply_text,
                provider=self.name,
                model=active_model,
                duration_sec=duration,
                tools_called=[{"tool": "grok_generate", "model": active_model, "duration_sec": round(duration, 3)}]
            )

        except Exception as e:
            category, is_retryable, clean_msg = self._classify_error(e, api_key)
            self._last_error = clean_msg
            raise ProviderException(
                message=clean_msg,
                category=category,
                is_retryable=is_retryable,
                provider=self.name,
                original_exc=e
            )

    def get_status(self) -> Dict[str, Any]:
        configured = self.is_configured()
        return {
            "name": self.name,
            "configured": configured,
            "model": self._cached_model or settings.XAI_MODEL,
            "available": configured and HAS_OPENAI,
            "last_error": self._last_error
        }
