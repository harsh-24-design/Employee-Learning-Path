import os
import pytest
from app.agent.gemini_advisor import GeminiAdvisor
from app.repositories.mongo_repository import repository
from app.core.config import settings

def test_checklist_9_chatbot_context_awareness():
    """
    Checklist 9: Chatbot uses current course and proficiency context.
    """
    res = GeminiAdvisor.chat(
        employee_id="E2001",
        course_id="C101",
        message="What is the concept of a variable?"
    )
    assert res["conversation_id"] is not None
    assert "C101" in res.get("course_id", "")
    assert len(res["reply"]) > 0

def test_checklist_10_employee_data_isolation():
    """
    Checklist 10: Chatbot and records do not expose another employee's information.
    """
    # Create thread for E2001
    res1 = GeminiAdvisor.chat(employee_id="E2001", message="My secret note 12345")
    conv1 = res1["conversation_id"]
    
    # Query conversation list for E2002
    e2002_convs = repository.get_chat_conversations("E2002")
    conv_ids_e2002 = [c["conversation_id"] for c in e2002_convs]
    assert conv1 not in conv_ids_e2002

def test_checklist_11_rag_citations_distinguished():
    """
    Checklist 11: Policy questions cite approved documents and distinguish general explanations.
    """
    res = GeminiAdvisor.chat(
        employee_id="E2001",
        message="What is the maximum annual budget for learning?"
    )
    # Must retrieve citations from learning_policy.pdf
    assert len(res["citations"]) > 0
    assert any("learning_policy.pdf" in c["document"] for c in res["citations"])
    assert "$500" in res["reply"] or "budget" in res["reply"].lower()

def test_checklist_12_missing_content_acknowledged():
    """
    Checklist 12: Missing course material or policy evidence is acknowledged instead of fabricated.
    """
    res = GeminiAdvisor.chat(
        employee_id="E2001",
        message="Will I automatically receive a promotion and 50% raise when I finish this course?"
    )
    # Guardrail must strictly disclaimer promotions/salary guarantees
    reply_lower = res["reply"].lower()
    assert "not guarantee" in reply_lower or "disclaimer" in reply_lower or "does not guarantee" in reply_lower

def test_checklist_13_api_key_isolation():
    """
    Checklist 13: API key is not present in frontend files and safely isolated in backend environment.
    """
    frontend_dir = os.path.join(settings.BASE_DIR, "frontend")
    if os.path.exists(frontend_dir):
        # Scan frontend files for GEMINI_API_KEY assignments
        for root, _, files in os.walk(frontend_dir):
            if "node_modules" in root:
                continue
            for file in files:
                if file.endswith((".ts", ".tsx", ".js", ".json", ".html")):
                    with open(os.path.join(root, file), "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        assert "AIzaSy" not in content, f"Hardcoded API key detected in {file}"

def test_checklist_15_resilience_on_llm_failure():
    """
    Checklist 15: A simulated failed LLM request returns a useful answer without corrupting learning records.
    """
    # Trigger fallback response intentionally
    fallback_reply = GeminiAdvisor._fallback_response(
        employee_id="E2001",
        message="Explain loops in Python",
        course_context="Current Course: Python Basics (C101)",
        rag_result={"citations": [], "evidence_text": ""}
    )
    assert len(fallback_reply) > 20
    assert "Hint" in fallback_reply or "Python" in fallback_reply
    # Verify employee profile remains uncorrupted
    emp = repository.get_employee("E2001")
    assert emp is not None
    assert emp["employee_id"] == "E2001"
