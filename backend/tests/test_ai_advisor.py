import os
import uuid
import pytest
from unittest.mock import MagicMock, patch
from app.agent.gemini_advisor import GeminiAdvisor, TUTOR_SYSTEM_PROMPT, FULL_SYSTEM_PROMPT
from app.repositories.mongo_repository import repository
from app.core.config import settings
from fastapi.testclient import TestClient
from app.main import app

GENERIC_HINT_TEMPLATE_SNIPPET = "1. Identify the input data structure and intended output."

@pytest.fixture
def mock_gemini_client():
    with patch("app.agent.gemini_advisor.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        yield mock_client

def test_ai_advisor_test_a_beginner_python(mock_gemini_client):
    """
    Test A:
    User: 'I am a complete beginner. Teach me Python from scratch.'
    Expected: A beginner-friendly introduction to Python and a first `print()` example.
    """
    mock_response = MagicMock()
    mock_response.text = (
        "Welcome to Python! Python is a beginner-friendly programming language.\n\n"
        "Here is your very first program:\n"
        "```python\n"
        "print('Hello, World!')\n"
        "```\n\n"
        "Line-by-line explanation:\n"
        "- `print()` is a built-in function that displays text on the screen.\n"
        "- `'Hello, World!'` is a string (text) passed inside the parentheses.\n\n"
        "Output:\n"
        "```text\n"
        "Hello, World!\n"
        "```\n\n"
        "Practice Question: What will `print('Welcome to Python!')` display on your screen?"
    )
    mock_gemini_client.models.generate_content.return_value = mock_response

    with patch.object(settings, "GEMINI_API_KEY", "test_gemini_key_12345"):
        res = GeminiAdvisor.chat(
            employee_id="E2001",
            course_id="C101",
            message="I am a complete beginner. Teach me Python from scratch."
        )

    # 1. Verify response content
    assert "print('Hello, World!')" in res["reply"]
    assert "beginner" in res["reply"].lower() or "welcome" in res["reply"].lower()
    
    # 2. Confirm generic hint template is NEVER returned
    assert GENERIC_HINT_TEMPLATE_SNIPPET not in res["reply"]

    # 3. Verify system prompt passed to Gemini contains the tutor prompt
    mock_gemini_client.models.generate_content.assert_called_once()
    call_kwargs = mock_gemini_client.models.generate_content.call_args[1]
    assert TUTOR_SYSTEM_PROMPT in call_kwargs["config"].system_instruction

def test_ai_advisor_test_b_python_variables(mock_gemini_client):
    """
    Test B:
    User: 'What is a variable in Python?'
    Expected: An explanation of variables with an example and output.
    """
    mock_response = MagicMock()
    mock_response.text = (
        "In Python, a variable is like a labeled container used to store data in memory.\n\n"
        "Code Example:\n"
        "```python\n"
        "user_name = 'Alex'\n"
        "learning_hours = 10\n"
        "print(user_name)\n"
        "print(learning_hours)\n"
        "```\n\n"
        "Output:\n"
        "```text\n"
        "Alex\n"
        "10\n"
        "```\n\n"
        "Practice Question: If you write `age = 25`, what type of data is stored in the variable `age`?"
    )
    mock_gemini_client.models.generate_content.return_value = mock_response

    with patch.object(settings, "GEMINI_API_KEY", "test_gemini_key_12345"):
        res = GeminiAdvisor.chat(
            employee_id="E2001",
            course_id="C101",
            message="What is a variable in Python?"
        )

    assert "variable" in res["reply"].lower()
    assert "user_name" in res["reply"] or "output" in res["reply"].lower()
    assert GENERIC_HINT_TEMPLATE_SNIPPET not in res["reply"]

def test_ai_advisor_test_c_python_if_else(mock_gemini_client):
    """
    Test C:
    User: 'Explain if-else in Python.'
    Expected: A relevant if-else explanation and example.
    """
    mock_response = MagicMock()
    mock_response.text = (
        "In Python, `if-else` statements allow your program to make decisions based on conditions.\n\n"
        "Code Example:\n"
        "```python\n"
        "score = 85\n"
        "if score >= 70:\n"
        "    print('Passed the assessment!')\n"
        "else:\n"
        "    print('Please review the concepts and try again.')\n"
        "```\n\n"
        "Output:\n"
        "```text\n"
        "Passed the assessment!\n"
        "```"
    )
    mock_gemini_client.models.generate_content.return_value = mock_response

    with patch.object(settings, "GEMINI_API_KEY", "test_gemini_key_12345"):
        res = GeminiAdvisor.chat(
            employee_id="E2001",
            course_id="C101",
            message="Explain if-else in Python."
        )

    assert "if" in res["reply"] and "else" in res["reply"]
    assert "Passed the assessment!" in res["reply"]
    assert GENERIC_HINT_TEMPLATE_SNIPPET not in res["reply"]

def test_ai_advisor_test_d_conversation_history_context(mock_gemini_client):
    """
    Test D:
    User: 'What did we learn in the previous lesson?'
    Expected: A context-aware answer based on actual conversation history, when available.
    """
    conv_id = f"CONV-TEST-D-{uuid.uuid4().hex[:6]}"
    
    # 1. First interaction: teach variables
    resp1 = MagicMock()
    resp1.text = "In our first lesson, we covered Python variables such as `name = 'Alex'`."
    mock_gemini_client.models.generate_content.return_value = resp1

    with patch.object(settings, "GEMINI_API_KEY", "test_gemini_key_12345"):
        GeminiAdvisor.chat(
            employee_id="E2001",
            conversation_id=conv_id,
            message="What is a variable in Python?"
        )

    # 2. Second interaction: ask what was learned
    resp2 = MagicMock()
    resp2.text = "In the previous lesson, we learned about Python variables and how to store values like strings and numbers."
    mock_gemini_client.models.generate_content.return_value = resp2

    with patch.object(settings, "GEMINI_API_KEY", "test_gemini_key_12345"):
        res2 = GeminiAdvisor.chat(
            employee_id="E2001",
            conversation_id=conv_id,
            message="What did we learn in the previous lesson?"
        )

    # Verify conversation history was passed in contents to Gemini
    call_args = mock_gemini_client.models.generate_content.call_args[1]
    contents_passed = call_args["contents"]
    
    # Must have more than 1 turn because history is included
    assert len(contents_passed) >= 2
    # Verify prior topic was referenced in contents
    combined_texts = " ".join([p.text for c in contents_passed for p in c.parts])
    assert "variable" in combined_texts.lower()
    
    # Verify assistant reply
    assert "previous lesson" in res2["reply"].lower() or "variable" in res2["reply"].lower()
    assert GENERIC_HINT_TEMPLATE_SNIPPET not in res2["reply"]

def test_ai_advisor_test_e_simulated_api_failure(mock_gemini_client):
    """
    Test E:
    Simulate an AI API failure.
    Expected: A clear error message, not the generic hint template.
    """
    mock_gemini_client.models.generate_content.side_effect = Exception("RateLimit: 429 Resource has been exhausted (quota exceeded)")

    with patch.object(settings, "GEMINI_API_KEY", "test_gemini_key_12345"):
        res = GeminiAdvisor.chat(
            employee_id="E2001",
            course_id="C101",
            message="Explain loops in Python."
        )

    # Must return clear error message describing failure
    assert "AI Service Error" in res["reply"]
    assert "429" in res["reply"] or "exhausted" in res["reply"]
    
    # Must NEVER silently return the generic hint template!
    assert GENERIC_HINT_TEMPLATE_SNIPPET not in res["reply"]

def test_ai_advisor_missing_api_key_configuration():
    """
    Test missing GEMINI_API_KEY:
    Expected: Clear configuration notice identifying the missing environment variable without exposing secrets.
    """
    with patch.object(settings, "GEMINI_API_KEY", ""):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=True):
            res = GeminiAdvisor.chat(
                employee_id="E2001",
                course_id="C101",
                message="Teach me Python from scratch."
            )

    assert "AI Advisor Configuration Notice" in res["reply"]
    assert "GEMINI_API_KEY" in res["reply"]
    assert GENERIC_HINT_TEMPLATE_SNIPPET not in res["reply"]

def test_ai_advisor_end_to_end_api_route(mock_gemini_client):
    """
    Test end-to-end FastAPI endpoint:
    POST /api/chat/conversations/{conv_id}/messages
    """
    mock_response = MagicMock()
    mock_response.text = "Hello! I am your personal tutor. What would you like to learn today?"
    mock_gemini_client.models.generate_content.return_value = mock_response

    client = TestClient(app)
    conv_id = f"CONV-E2E-{uuid.uuid4().hex[:6]}"

    # Login to obtain Bearer token
    login_res = client.post("/api/auth/login", json={"email": "employee@example.com", "password": "employee123"})
    assert login_res.status_code == 200
    token = login_res.json()["token"]

    with patch.object(settings, "GEMINI_API_KEY", "test_gemini_key_12345"):
        res = client.post(
            f"/api/chat/conversations/{conv_id}/messages",
            json={
                "employee_id": "E2001",
                "message": "Hello tutor!",
                "course_id": "C101",
                "plan_mode": "self_directed"
            },
            headers={"Authorization": f"Bearer {token}"}
        )

    assert res.status_code == 200
    data = res.json()
    assert data["conversation_id"] == conv_id
    assert "personal tutor" in data["reply"]
    assert GENERIC_HINT_TEMPLATE_SNIPPET not in data["reply"]

def test_dynamic_model_verification():
    """
    Test that dynamic model verification queries client.models.list()
    and selects an available free-tier model.
    """
    mock_client = MagicMock()
    # Simulate models returned from Gemini API
    m1 = MagicMock()
    m1.name = "models/gemini-1.5-flash"
    m1.supported_actions = ["generateContent"]

    m2 = MagicMock()
    m2.name = "models/text-embedding-004"
    m2.supported_actions = ["embedContent"]

    mock_client.models.list.return_value = [m1, m2]

    # Reset cache
    GeminiAdvisor._cached_model = None
    GeminiAdvisor._cached_model_time = None

    selected = GeminiAdvisor.get_verified_model(mock_client, preferred_model="gemini-non-existent")
    assert selected == "gemini-1.5-flash"

def test_error_handling_invalid_api_key():
    """
    Test specific error message when API key is invalid (400/403 API_KEY_INVALID).
    """
    err = Exception("ClientError: 400 API_KEY_INVALID. API key not valid. Please pass a valid API key.")
    formatted = GeminiAdvisor._format_error_message(err, api_key="secret_key_123", model_name="gemini-2.0-flash")
    assert "Invalid API Key" in formatted
    assert "Google AI Studio" in formatted
    assert "secret_key_123" not in formatted

def test_error_handling_quota_exceeded():
    """
    Test specific error message when quota/rate limit is exceeded (429 RESOURCE_EXHAUSTED).
    """
    err = Exception("ResourceExhausted: 429 Quota exceeded for quota metric 'Queries' and limit 'QUOTA_FOR_DEFAULT_TIER'.")
    formatted = GeminiAdvisor._format_error_message(err, api_key="secret_key_123", model_name="gemini-2.0-flash")
    assert "429 Quota Exceeded" in formatted
    assert "secret_key_123" not in formatted

def test_error_handling_model_unavailable():
    """
    Test specific error message when requested model is unavailable (404 NOT_FOUND).
    """
    err = Exception("NotFound: 404 models/gemini-custom is not found for API version v1beta.")
    formatted = GeminiAdvisor._format_error_message(err, api_key="secret_key_123", model_name="gemini-custom")
    assert "404 Model Unavailable" in formatted
    assert "gemini-custom" in formatted
    assert "secret_key_123" not in formatted

def test_error_handling_network_connection_failure():
    """
    Test specific error message when network connection fails.
    """
    err = ConnectionError("Failed to establish a new connection: [WinError 10060] A connection attempt failed because the connected party did not properly respond.")
    formatted = GeminiAdvisor._format_error_message(err, api_key="secret_key_123", model_name="gemini-2.0-flash")
    assert "Network Connection Failure" in formatted
    assert "secret_key_123" not in formatted

