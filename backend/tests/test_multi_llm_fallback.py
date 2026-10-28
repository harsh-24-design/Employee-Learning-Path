import os
import time
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.agent.gemini_advisor import GeminiAdvisor
from app.agent.providers.base import LLMMessage, ErrorCategory, ProviderException
from app.agent.providers.fallback_manager import LLMFallbackManager, fallback_manager
from app.agent.providers.openai_provider import OpenAIProvider
from app.agent.providers.grok_provider import GrokProvider
from app.agent.providers.gemini_provider import GeminiProvider

client = TestClient(app)

def test_gemini_success_primary():
    """
    1. Gemini succeeds as primary provider.
    Backup providers (OpenAI, Grok) must NOT be called.
    """
    mock_gemini_reply = "Gemini Response: A variable in Python stores data values."
    
    with patch.object(settings, "LLM_PRIMARY_PROVIDER", "gemini"), \
         patch.object(settings, "LLM_FALLBACK_ORDER", "gemini,openai,grok"), \
         patch.object(settings, "get_gemini_api_keys", return_value=["valid-gemini-key"]), \
         patch.object(settings, "OPENAI_API_KEY", "valid-openai-key"), \
         patch.object(settings, "XAI_API_KEY", "valid-xai-key"):
        
        with patch.object(GeminiAdvisor, "_execute_gemini_call", return_value=(mock_gemini_reply, [{"tool": "gemini_generate", "model": "gemini-2.0-flash"}])) as mock_gemini, \
             patch.object(OpenAIProvider, "generate") as mock_openai, \
             patch.object(GrokProvider, "generate") as mock_grok:
            
            res = GeminiAdvisor.chat(
                employee_id="E2001",
                course_id="C101",
                message="What is a Python variable?"
            )
            
            assert mock_gemini_reply in res["reply"]
            assert any(t.get("tool") == "gemini_generate" for t in res["tools_called"])
            mock_gemini.assert_called_once()
            mock_openai.assert_not_called()
            mock_grok.assert_not_called()

def test_gemini_failure_followed_by_openai_success():
    """
    2. Gemini fails with rate limit / 429 quota exhaustion.
    System automatically fails over to OpenAI. Grok is not called.
    """
    mock_openai_reply = "OpenAI Response: In Python, variables are created when you assign a value to them."
    
    with patch.object(settings, "LLM_PRIMARY_PROVIDER", "gemini"), \
         patch.object(settings, "LLM_FALLBACK_ORDER", "gemini,openai,grok"), \
         patch.object(settings, "get_gemini_api_keys", return_value=["gemini-quota-key"]), \
         patch.object(settings, "OPENAI_API_KEY", "openai-valid-key"), \
         patch.object(settings, "XAI_API_KEY", "xai-valid-key"):
        
        with patch.object(GeminiAdvisor, "_execute_gemini_call", side_effect=Exception("429 Resource Exhausted: Quota exceeded for model gemini-2.0-flash")), \
             patch.object(OpenAIProvider, "is_configured", return_value=True), \
             patch.object(OpenAIProvider, "generate") as mock_openai, \
             patch.object(GrokProvider, "generate") as mock_grok:
            
            from app.agent.providers.base import LLMResponse
            mock_openai.return_value = LLMResponse(
                text=mock_openai_reply,
                provider="openai",
                model="gpt-4o-mini",
                duration_sec=0.45,
                tools_called=[{"tool": "openai_generate", "model": "gpt-4o-mini"}]
            )
            
            res = GeminiAdvisor.chat(
                employee_id="E2001",
                course_id="C101",
                message="What is a Python variable?"
            )
            
            assert mock_openai_reply in res["reply"]
            assert any(t.get("tool") == "openai_generate" for t in res["tools_called"])
            mock_openai.assert_called_once()
            mock_grok.assert_not_called()

def test_gemini_and_openai_failure_followed_by_grok_success():
    """
    3. Gemini and OpenAI both fail.
    System automatically fails over to xAI Grok.
    """
    mock_grok_reply = "Grok Response: A Python variable is essentially a symbolic name bound to an object."
    
    with patch.object(settings, "LLM_PRIMARY_PROVIDER", "gemini"), \
         patch.object(settings, "LLM_FALLBACK_ORDER", "gemini,openai,grok"), \
         patch.object(settings, "get_gemini_api_keys", return_value=["gemini-key"]), \
         patch.object(settings, "OPENAI_API_KEY", "openai-key"), \
         patch.object(settings, "XAI_API_KEY", "xai-key"):
        
        with patch.object(GeminiAdvisor, "_execute_gemini_call", side_effect=Exception("429 Quota exhausted")), \
             patch.object(OpenAIProvider, "is_configured", return_value=True), \
             patch.object(OpenAIProvider, "generate", side_effect=Exception("503 Service Unavailable")), \
             patch.object(GrokProvider, "is_configured", return_value=True), \
             patch.object(GrokProvider, "generate") as mock_grok:
            
            from app.agent.providers.base import LLMResponse
            mock_grok.return_value = LLMResponse(
                text=mock_grok_reply,
                provider="grok",
                model="grok-3-mini",
                duration_sec=0.62,
                tools_called=[{"tool": "grok_generate", "model": "grok-3-mini"}]
            )
            
            res = GeminiAdvisor.chat(
                employee_id="E2001",
                course_id="C101",
                message="What is a Python variable?"
            )
            
            assert mock_grok_reply in res["reply"]
            assert any(t.get("tool") == "grok_generate" for t in res["tools_called"])
            mock_grok.assert_called_once()

def test_all_providers_failing_returns_user_friendly_error():
    """
    4. All providers fail.
    Returns clear, user-friendly error without leaking credentials or crashing.
    """
    with patch.object(settings, "LLM_PRIMARY_PROVIDER", "gemini"), \
         patch.object(settings, "LLM_FALLBACK_ORDER", "gemini,openai,grok"), \
         patch.object(settings, "get_gemini_api_keys", return_value=["gemini-secret-123"]), \
         patch.object(settings, "OPENAI_API_KEY", "openai-secret-456"), \
         patch.object(settings, "XAI_API_KEY", "xai-secret-789"):
        
        with patch.object(GeminiAdvisor, "_execute_gemini_call", side_effect=Exception("Gemini server 500")), \
             patch.object(OpenAIProvider, "is_configured", return_value=True), \
             patch.object(OpenAIProvider, "generate", side_effect=Exception("OpenAI server 502")), \
             patch.object(GrokProvider, "is_configured", return_value=True), \
             patch.object(GrokProvider, "generate", side_effect=Exception("Grok server 504")):
            
            res = GeminiAdvisor.chat(
                employee_id="E2001",
                course_id="C101",
                message="What is a Python variable?"
            )
            
            assert "AI Service Error" in res["reply"]
            # Assert credentials are NEVER leaked
            assert "gemini-secret-123" not in res["reply"]
            assert "openai-secret-456" not in res["reply"]
            assert "xai-secret-789" not in res["reply"]

def test_invalid_api_key_immediate_failover():
    """
    5. Permanent authentication error (401 / 403 API key invalid).
    Must NOT retry invalid credentials; immediately falls over to OpenAI.
    """
    with patch.object(settings, "LLM_PRIMARY_PROVIDER", "gemini"), \
         patch.object(settings, "LLM_FALLBACK_ORDER", "gemini,openai"), \
         patch.object(settings, "get_gemini_api_keys", return_value=["invalid-gemini-key"]), \
         patch.object(settings, "OPENAI_API_KEY", "valid-openai-key"):
        
        call_count = 0
        def mock_gemini_auth_err(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise Exception("400 API_KEY_INVALID: API key not valid. Please pass a valid API key.")
        
        with patch.object(GeminiAdvisor, "_execute_gemini_call", side_effect=mock_gemini_auth_err), \
             patch.object(OpenAIProvider, "is_configured", return_value=True), \
             patch.object(OpenAIProvider, "generate") as mock_openai:
            
            from app.agent.providers.base import LLMResponse
            mock_openai.return_value = LLMResponse(
                text="OpenAI answer after invalid key failover",
                provider="openai",
                model="gpt-4o-mini",
                duration_sec=0.3
            )
            
            res = GeminiAdvisor.chat(
                employee_id="E2001",
                course_id="C101",
                message="What is a Python variable?"
            )
            
            # Exactly 1 call attempted on invalid key, no repeated loop
            assert call_count == 1
            assert "OpenAI answer" in res["reply"]

def test_connection_timeout_triggers_fallback():
    """
    6. Connection timeout on primary provider triggers fallback to secondary.
    """
    with patch.object(settings, "LLM_PRIMARY_PROVIDER", "gemini"), \
         patch.object(settings, "LLM_FALLBACK_ORDER", "gemini,openai"), \
         patch.object(settings, "get_gemini_api_keys", return_value=["timeout-gemini-key"]), \
         patch.object(settings, "OPENAI_API_KEY", "valid-openai-key"):
        
        with patch.object(GeminiAdvisor, "_execute_gemini_call", side_effect=TimeoutError("Request timed out after 30 seconds")), \
             patch.object(OpenAIProvider, "is_configured", return_value=True), \
             patch.object(OpenAIProvider, "generate") as mock_openai:
            
            from app.agent.providers.base import LLMResponse
            mock_openai.return_value = LLMResponse(
                text="OpenAI handled request after Gemini timeout",
                provider="openai",
                model="gpt-4o-mini",
                duration_sec=0.25
            )
            
            res = GeminiAdvisor.chat(
                employee_id="E2001",
                course_id="C101",
                message="What is a Python variable?"
            )
            
            assert "OpenAI handled request after Gemini timeout" in res["reply"]

def test_missing_credentials_skipped_cleanly():
    """
    7. Unconfigured providers are skipped cleanly without errors.
    Primary provider is Gemini (unconfigured), OpenAI is configured.
    OpenAI is called directly.
    """
    with patch.object(settings, "LLM_PRIMARY_PROVIDER", "gemini"), \
         patch.object(settings, "LLM_FALLBACK_ORDER", "gemini,openai,grok"), \
         patch.object(settings, "get_gemini_api_keys", return_value=[]), \
         patch.object(settings, "OPENAI_API_KEY", "valid-openai-key"), \
         patch.object(settings, "XAI_API_KEY", ""):
        
        with patch.object(OpenAIProvider, "is_configured", return_value=True), \
             patch.object(OpenAIProvider, "generate") as mock_openai:
            
            from app.agent.providers.base import LLMResponse
            mock_openai.return_value = LLMResponse(
                text="OpenAI direct response when Gemini has no key",
                provider="openai",
                model="gpt-4o-mini",
                duration_sec=0.2
            )
            
            res = GeminiAdvisor.chat(
                employee_id="E2001",
                course_id="C101",
                message="What is a Python variable?"
            )
            
            assert "OpenAI direct response" in res["reply"]

def test_missing_all_provider_credentials_clear_notice():
    """
    8. When zero providers are configured, returns clear configuration guidance.
    """
    with patch.object(settings, "LLM_PRIMARY_PROVIDER", "gemini"), \
         patch.object(settings, "get_gemini_api_keys", return_value=[]), \
         patch.object(settings, "OPENAI_API_KEY", ""), \
         patch.object(settings, "XAI_API_KEY", ""):
        
        with patch.object(OpenAIProvider, "is_configured", return_value=False), \
             patch.object(GrokProvider, "is_configured", return_value=False):
            
            res = GeminiAdvisor.chat(
                employee_id="E2001",
                course_id="C101",
                message="What is a Python variable?"
            )
            
            assert "AI Advisor Configuration Notice" in res["reply"]
            assert "GEMINI_API_KEY" in res["reply"]

def test_invalid_model_configuration_fallback_candidate():
    """
    9. Dynamic model verification validates model against provider model list,
    falling back to candidate models if preferred model is unavailable.
    """
    mock_client = MagicMock()
    m1 = MagicMock()
    m1.id = "gpt-4o-mini"
    m2 = MagicMock()
    m2.id = "gpt-4o"
    mock_client.models.list.return_value = [m1, m2]
    
    provider = OpenAIProvider()
    provider._cached_model = None
    provider._cached_model_time = None
    
    # Preferred model is unsupported / unavailable
    selected = provider.get_verified_model(mock_client, preferred_model="gpt-unsupported-model")
    assert selected == "gpt-4o-mini"

def test_preservation_of_rag_context_and_conversation_history():
    """
    10. Verify that conversation history, retrieved RAG chunks, active course metadata,
    and system prompts are fully preserved when failover occurs to OpenAI.
    """
    with patch.object(settings, "LLM_PRIMARY_PROVIDER", "gemini"), \
         patch.object(settings, "LLM_FALLBACK_ORDER", "gemini,openai"), \
         patch.object(settings, "get_gemini_api_keys", return_value=["gemini-key"]), \
         patch.object(settings, "OPENAI_API_KEY", "openai-key"):
        
        captured_messages = None
        captured_system = None
        
        def mock_openai_generate(messages, system_prompt, **kwargs):
            nonlocal captured_messages, captured_system
            captured_messages = messages
            captured_system = system_prompt
            from app.agent.providers.base import LLMResponse
            return LLMResponse(
                text="OpenAI grounded answer with preserved RAG",
                provider="openai",
                model="gpt-4o-mini",
                duration_sec=0.2
            )
        
        with patch.object(GeminiAdvisor, "_execute_gemini_call", side_effect=Exception("Gemini quota 429")), \
             patch.object(OpenAIProvider, "is_configured", return_value=True), \
             patch.object(OpenAIProvider, "generate", side_effect=mock_openai_generate):
            
            res = GeminiAdvisor.chat(
                employee_id="E2001",
                course_id="C101",
                message="What is a Python variable?"
            )
            
            assert "OpenAI grounded answer" in res["reply"]
            assert captured_system is not None
            assert "AI Learning Advisor" in captured_system or "Python" in captured_system
            
            # Assert user prompt received by OpenAI contains active course metadata and RAG evidence
            assert captured_messages is not None
            user_msg = captured_messages[-1].content
            assert "Python Basics" in user_msg
            assert "Retrieved Course Material" in user_msg or "Variables" in user_msg
            assert "Learner Question: What is a Python variable?" in user_msg

def test_safe_status_endpoint_no_secret_leak():
    """
    11. Safe status endpoint (/api/llm/status) exposes debugging info without leaking credentials.
    """
    with patch.object(settings, "GEMINI_API_KEY", "secret-gemini-key-12345"), \
         patch.object(settings, "OPENAI_API_KEY", "secret-openai-key-67890"), \
         patch.object(settings, "XAI_API_KEY", "secret-xai-key-54321"):
        
        res = client.get("/api/llm/status")
        assert res.status_code == 200
        data = res.json()
        
        assert "primary_provider" in data
        assert "fallback_order" in data
        assert "providers" in data
        assert len(data["providers"]) == 3
        
        # Verify providers metadata exists
        provider_names = [p["name"] for p in data["providers"]]
        assert "gemini" in provider_names
        assert "openai" in provider_names
        assert "grok" in provider_names
        
        # Verify NO secret credentials leaked in payload text
        response_text = res.text
        assert "secret-gemini-key-12345" not in response_text
        assert "secret-openai-key-67890" not in response_text
        assert "secret-xai-key-54321" not in response_text
