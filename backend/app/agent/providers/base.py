import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple

class ErrorCategory(str, Enum):
    RATE_LIMIT_429 = "rate_limit_or_quota_exhausted"
    AUTH_INVALID_KEY = "invalid_or_revoked_api_key"
    MODEL_UNAVAILABLE = "model_unavailable_or_not_found"
    NETWORK_TIMEOUT = "network_connection_or_timeout"
    SERVER_ERROR_5XX = "provider_server_error_5xx"
    MALFORMED_RESPONSE = "malformed_response"
    CONFIG_MISSING = "credentials_missing_or_unconfigured"
    UNKNOWN = "unknown_error"

@dataclass
class LLMMessage:
    role: str  # "system", "user", "assistant"
    content: str

@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    duration_sec: float
    tools_called: List[Dict[str, Any]] = field(default_factory=list)
    finish_reason: str = "stop"
    raw_usage: Optional[Dict[str, Any]] = None

class ProviderException(Exception):
    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        is_retryable: bool,
        provider: str,
        original_exc: Optional[Exception] = None
    ):
        super().__init__(message)
        self.category = category
        self.is_retryable = is_retryable
        self.provider = provider
        self.original_exc = original_exc

def redact_secrets(text: str, secrets_to_redact: Optional[List[str]] = None) -> str:
    """
    Sanitizes any secret API keys or credentials from text or exception messages.
    """
    if not text:
        return ""
    
    clean = str(text)
    if secrets_to_redact:
        for s in secrets_to_redact:
            if s and len(s) > 4 and s in clean:
                clean = clean.replace(s, "[REDACTED]")

    # Generic patterns for API keys (e.g. AIzaSy..., sk-..., xai-...)
    clean = re.sub(r'AIzaSy[A-Za-z0-9_-]{30,}', '[REDACTED_GEMINI_KEY]', clean)
    clean = re.sub(r'sk-[A-Za-z0-9_-]{20,}', '[REDACTED_OPENAI_KEY]', clean)
    clean = re.sub(r'xai-[A-Za-z0-9_-]{20,}', '[REDACTED_XAI_KEY]', clean)
    return clean

class BaseLLMProvider(ABC):
    """
    Common abstraction for LLM providers (Gemini, OpenAI, xAI Grok).
    Each provider implements model verification, message formatting,
    execution with timeouts, and isolated error handling.
    """
    name: str

    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if the provider has valid credentials configured."""
        pass

    @abstractmethod
    def get_verified_model(self, preferred_model: Optional[str] = None) -> str:
        """Validates that the target model is available, falling back to verified alternatives."""
        pass

    @abstractmethod
    def generate(
        self,
        messages: List[LLMMessage],
        system_prompt: str,
        temperature: float = 0.7,
        timeout: Optional[float] = None
    ) -> LLMResponse:
        """Executes a completion request and returns a normalized LLMResponse."""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Returns safe provider health and configuration metadata without credentials."""
        pass
