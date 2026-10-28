import time
import logging
from typing import List, Dict, Any, Optional, Tuple

from app.core.config import settings
from app.agent.providers.base import (
    BaseLLMProvider,
    LLMMessage,
    LLMResponse,
    ErrorCategory,
    ProviderException,
    redact_secrets
)

logger = logging.getLogger("learning_agent.providers.gemini")

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    genai = None
    types = None
    HAS_GENAI = False

class GeminiProvider(BaseLLMProvider):
    name = "gemini"

    _FREE_TIER_CANDIDATES = [
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash-8b",
        "gemini-2.5-flash",
        "gemini-1.5-pro"
    ]

    def __init__(self):
        self._cached_model: Optional[str] = None
        self._cached_model_time: Optional[float] = None
        self._last_error: Optional[str] = None

    def is_configured(self) -> bool:
        if not HAS_GENAI:
            return False
        keys = settings.get_gemini_api_keys()
        return len(keys) > 0

    def get_verified_model(self, client: Any = None, preferred_model: Optional[str] = None) -> str:
        now = time.time()
        if self._cached_model and self._cached_model_time and (now - self._cached_model_time < 3600):
            return self._cached_model

        target = preferred_model or settings.GEMINI_MODEL or "gemini-2.0-flash"

        if client is not None and hasattr(client, "models") and hasattr(client.models, "list"):
            try:
                available_names = set()
                models_pager = client.models.list()
                for m in models_pager:
                    raw_name = getattr(m, "name", "") or ""
                    clean_name = raw_name.split("/")[-1]
                    supported = getattr(m, "supported_actions", None)
                    if supported is None or "generateContent" in supported:
                        available_names.add(clean_name)
                        available_names.add(raw_name)

                if target in available_names or f"models/{target}" in available_names:
                    self._cached_model = target
                    self._cached_model_time = now
                    return target

                for candidate in self._FREE_TIER_CANDIDATES:
                    if candidate in available_names or f"models/{candidate}" in available_names:
                        self._cached_model = candidate
                        self._cached_model_time = now
                        return candidate

                gemini_models = [m for m in available_names if "gemini" in m.lower() and not m.startswith("models/")]
                if gemini_models:
                    self._cached_model = gemini_models[0]
                    self._cached_model_time = now
                    return gemini_models[0]
            except Exception as e:
                logger.debug(f"Gemini model list verification error: {e}")

        self._cached_model = target
        self._cached_model_time = now
        return target

    def _classify_error(self, e: Exception, keys: List[str]) -> Tuple[ErrorCategory, bool, str]:
        msg = str(e)
        clean_msg = redact_secrets(msg, keys)
        err_lower = clean_msg.lower()
        err_code = getattr(e, "code", None)

        if (
            "api_key_invalid" in err_lower
            or "api key not valid" in err_lower
            or "permission_denied" in err_lower
            or (err_code in (400, 401, 403) and any(w in err_lower for w in ["key", "credential", "auth", "token"]))
        ):
            return (
                ErrorCategory.AUTH_INVALID_KEY,
                False,
                "Gemini API key is invalid or unauthorized."
            )

        if (
            err_code == 429
            or "429" in clean_msg
            or "resource_exhausted" in err_lower
            or "quota" in err_lower
            or "rate limit" in err_lower
        ):
            return (
                ErrorCategory.RATE_LIMIT_429,
                True,
                "Gemini API rate limit or quota exceeded (429)."
            )

        if (
            err_code == 404
            or "404" in clean_msg
            or "not_found" in err_lower
            or ("model" in err_lower and ("not found" in err_lower or "unsupported" in err_lower))
        ):
            return (
                ErrorCategory.MODEL_UNAVAILABLE,
                False,
                f"Gemini model '{self._cached_model or settings.GEMINI_MODEL}' is unavailable or not found."
            )

        if any(w in err_lower for w in ["timeout", "timed out", "connecterror", "connection error", "connection refused", "winerror 10054", "winerror 10060"]):
            return (
                ErrorCategory.NETWORK_TIMEOUT,
                True,
                "Gemini network connection failure or timeout."
            )

        if err_code in (500, 502, 503, 504) or any(w in err_lower for w in ["500", "502", "503", "504", "internal error", "bad gateway"]):
            return (
                ErrorCategory.SERVER_ERROR_5XX,
                True,
                "Gemini upstream server 5xx error."
            )

        return (
            ErrorCategory.UNKNOWN,
            False,
            f"Gemini execution error: {clean_msg}"
        )

    def generate(
        self,
        messages: List[LLMMessage],
        system_prompt: str,
        temperature: float = 0.7,
        timeout: Optional[float] = None
    ) -> LLMResponse:
        if not HAS_GENAI:
            raise ProviderException(
                message="google-genai SDK is not installed.",
                category=ErrorCategory.CONFIG_MISSING,
                is_retryable=False,
                provider=self.name
            )

        keys = settings.get_gemini_api_keys()
        if not keys:
            raise ProviderException(
                message="GEMINI_API_KEY is not configured.",
                category=ErrorCategory.CONFIG_MISSING,
                is_retryable=False,
                provider=self.name
            )

        start_time = time.time()
        last_exception = None

        # Key rotation loop: iterate through configured keys
        for key_idx, active_key in enumerate(keys):
            try:
                client = genai.Client(api_key=active_key)
                active_model = self.get_verified_model(client)

                # Format messages for Gemini
                contents = []
                for m in messages:
                    if not m.content.strip():
                        continue
                    role = "user" if m.role == "user" else "model"
                    contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m.content)]))

                # Normalize alternating roles
                normalized: List[Any] = []
                for c in contents:
                    if normalized and normalized[-1].role == c.role:
                        normalized[-1].parts.extend(c.parts)
                    else:
                        normalized.append(c)

                while normalized and normalized[0].role != "user":
                    normalized.pop(0)

                if not normalized:
                    normalized.append(types.Content(role="user", parts=[types.Part.from_text(text="Hello")]))

                config = types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temperature
                )

                response = client.models.generate_content(
                    model=active_model,
                    contents=normalized,
                    config=config
                )

                duration = time.time() - start_time
                reply_text = getattr(response, "text", None) or "I have processed your request."
                self._last_error = None

                return LLMResponse(
                    text=reply_text,
                    provider=self.name,
                    model=active_model,
                    duration_sec=duration,
                    tools_called=[{"tool": "gemini_generate", "model": active_model, "duration_sec": round(duration, 3)}]
                )

            except Exception as e:
                category, is_retryable, clean_msg = self._classify_error(e, keys)
                last_exception = ProviderException(
                    message=clean_msg,
                    category=category,
                    is_retryable=is_retryable,
                    provider=self.name,
                    original_exc=e
                )
                self._last_error = clean_msg

                # If quota/rate limit error (429) and more keys exist, attempt rotation
                if category == ErrorCategory.RATE_LIMIT_429 and key_idx < len(keys) - 1:
                    logger.warning("Gemini key hit quota; rotating to secondary key silently.")
                    continue

                # Permanent error or all keys exhausted
                raise last_exception

        if last_exception:
            raise last_exception
        raise ProviderException(
            message="Gemini provider failed unexpectedly.",
            category=ErrorCategory.UNKNOWN,
            is_retryable=False,
            provider=self.name
        )

    def get_status(self) -> Dict[str, Any]:
        keys = settings.get_gemini_api_keys()
        return {
            "name": self.name,
            "configured": len(keys) > 0,
            "model": self._cached_model or settings.GEMINI_MODEL,
            "available": len(keys) > 0 and HAS_GENAI,
            "keys_configured_count": len(keys),
            "last_error": self._last_error
        }
