import os
import json
import uuid
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from app.core.config import settings
from app.services.policy_rag import PolicyRAGService
from app.services.course_rag import CourseRAGService
from app.repositories.mongo_repository import repository

try:
    from google import genai
    from google.genai import types, errors
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False
    types = None
    errors = None

TUTOR_SYSTEM_PROMPT = """You are a Course-Aware Personal Learning Tutor. Your job is to help learners master concepts grounded strictly in the verified course lesson material provided in the context.

When answering learner questions:
1. Provide a clear, substantive explanation based directly on the retrieved course lesson material.
2. Provide a relevant practical example (such as a Python code snippet, Excel formula scenario, or cloud architecture diagram/example) and show the expected output or result.
3. Include an explicit source citation in the format: [Course Title - Module Title: Lesson Title] referencing the lesson used.
4. Conclude with exactly ONE targeted practice question for the learner to reinforce their understanding.
5. If the retrieved material does not cover the question, state clearly that the answer was not found in the course material. Do not invent facts, hallucinate concepts, or fabricate course citations."""

RESPONSIBLE_AI_GUARDRAILS = """
CRITICAL RESPONSIBLE AI & ADVISORY GUARDRAILS:
1. NEVER guarantee certification, formal promotion, salary increases, bonus awards, or specific employment outcomes under any circumstances.
2. RECOMMEND ONLY courses that exist in the approved catalogue. Never invent or hallucinate course names or IDs.
3. GROUND corporate policy questions strictly in approved corporate documents. When evidence is insufficient or missing, clearly state that evidence is unavailable.
4. Adapt explanations to the employee's current skill level (beginner, intermediate, advanced).
5. When explaining credentials, distinguish clearly between completion certificates, assessed course certificates, professional certificates, and accredited qualifications.
"""

FULL_SYSTEM_PROMPT = f"{TUTOR_SYSTEM_PROMPT}\n\n{RESPONSIBLE_AI_GUARDRAILS}"

class GeminiAdvisor:
    """
    Course-aware & Mode-aware conversational tutor connecting to Google Gemini API
    with multi-key failover/rotation, Chroma vector RAG retrieval, multi-turn history,
    and strict responsible AI guardrails.
    """

    _cached_model: Optional[str] = None
    _cached_model_time: Optional[float] = None

    _FREE_TIER_CANDIDATES = [
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash-8b",
        "gemini-2.5-flash",
        "gemini-1.5-pro"
    ]

    @classmethod
    def get_verified_model(cls, client: Any, preferred_model: Optional[str] = None) -> str:
        now = time.time()
        if cls._cached_model and cls._cached_model_time and (now - cls._cached_model_time < 3600):
            return cls._cached_model

        target = preferred_model or settings.GEMINI_MODEL or "gemini-2.0-flash"

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
                cls._cached_model = target
                cls._cached_model_time = now
                return target

            for candidate in cls._FREE_TIER_CANDIDATES:
                if candidate in available_names or f"models/{candidate}" in available_names:
                    cls._cached_model = candidate
                    cls._cached_model_time = now
                    return candidate

            gemini_models = [m for m in available_names if "gemini" in m.lower() and not m.startswith("models/")]
            if gemini_models:
                cls._cached_model = gemini_models[0]
                cls._cached_model_time = now
                return gemini_models[0]

        except Exception:
            pass

        cls._cached_model = target
        cls._cached_model_time = now
        return target

    @classmethod
    def _format_error_message(
        cls,
        e: Exception,
        api_key: Optional[str] = None,
        api_keys: Optional[List[str]] = None,
        model_name: str = ""
    ) -> str:
        err_msg = str(e)
        redact_list = []
        if api_key:
            redact_list.append(api_key)
        if api_keys:
            redact_list.extend(api_keys)

        for k in redact_list:
            if k and k in err_msg:
                err_msg = err_msg.replace(k, "[REDACTED]")

        err_lower = err_msg.lower()
        err_code = getattr(e, "code", None)

        if (
            "api_key_invalid" in err_lower
            or "api key not valid" in err_lower
            or "permission_denied" in err_lower
            or (err_code in (400, 403) and any(w in err_lower for w in ["key", "credential", "auth", "token"]))
        ):
            return (
                "AI Service Error (Invalid API Key): The configured GEMINI_API_KEY is invalid or unauthorized. "
                "Please verify your API key in Google AI Studio (https://aistudio.google.com/app/apikey) "
                "and ensure Gemini API access is enabled."
            )

        if (
            err_code == 429
            or "429" in err_msg
            or "resource_exhausted" in err_lower
            or "quota" in err_lower
            or "rate limit" in err_lower
        ):
            return (
                "AI Service Error (429 Quota Exceeded): Your Gemini API quota or rate limit has been reached. "
                "Please wait a few moments before trying again or configure a fallback key."
            )

        if (
            err_code == 404
            or "404" in err_msg
            or "not_found" in err_lower
            or ("model" in err_lower and ("not found" in err_lower or "unsupported" in err_lower))
        ):
            return (
                f"AI Service Error (404 Model Unavailable): The Gemini model '{model_name}' is currently unavailable "
                f"or not supported for your API key. Please check model availability or update GEMINI_MODEL."
            )

        if any(w in err_lower for w in ["connecterror", "connection error", "timeout", "network", "getaddrinfo failed", "connection refused", "winerror 10054", "winerror 10060"]):
            return (
                "AI Service Error (Network Connection Failure): Unable to reach the Google Gemini API server. "
                "Please verify your network connection, proxy, or firewall settings."
            )

        return (
            f"AI Service Error: Failed to generate response from Gemini API ({type(e).__name__}: {err_msg}). "
            f"Please check your API key, network connection, or try again later."
        )

    @classmethod
    def chat(
        cls,
        employee_id: str,
        message: str,
        course_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        plan_mode: Optional[str] = "self_directed"
    ) -> Dict[str, Any]:
        now_str = datetime.now(timezone.utc).isoformat()
        if not conversation_id:
            conversation_id = f"CONV-{uuid.uuid4().hex[:10].upper()}"
            repository.insert("chat_conversations", {
                "conversation_id": conversation_id,
                "employee_id": employee_id,
                "course_id": course_id,
                "title": f"Doubt Resolution: {course_id or 'General'}",
                "created_at": now_str,
                "updated_at": now_str
            })

        prior_messages = repository.get_chat_messages(conversation_id)

        # Save user message
        repository.insert("chat_messages", {
            "message_id": f"MSG-{uuid.uuid4().hex[:8]}",
            "conversation_id": conversation_id,
            "employee_id": employee_id,
            "sender": "user",
            "message": message,
            "course_id": course_id,
            "created_at": now_str
        })

        # Load course details
        course = None
        course_title = "General Learning"
        course_context = ""
        current_level = 1

        if course_id:
            course = repository.get_course(course_id)
            if course:
                course_title = course.get("title", course_id)
                cert_info = course.get("certificate_info", {})
                course_context = (
                    f"Current Active Course: {course.get('title')} (ID: {course.get('course_id')})\n"
                    f"Platform: {course.get('platform', 'Internal')}, Skill: {course.get('skill')}, Level: {course.get('level')}\n"
                    f"Pricing Model: {course.get('pricing_model', 'free')}, Cost: ${course.get('cost', 0)}\n"
                    f"Certificate: {cert_info.get('type', 'none')} by {cert_info.get('issuer', 'N/A')}\n"
                    f"Learning Mode: {'Company-Assigned Requirement' if plan_mode == 'company_assigned' else 'Self-Directed Personal Development'}\n"
                )
                emp_skills = repository.get_employee_skills(employee_id)
                for s in emp_skills:
                    if s.get("skill", "").lower() == course.get("skill", "").lower():
                        current_level = s.get("verified_level") or s.get("self_assessed_level", 1)
                        break
                course_context += f"Learner Current Proficiency Level: {current_level}/5\n"

        # Check for policy RAG evidence
        policy_rag = PolicyRAGService.search_policy(message, top_k=2)

        # Check for Chroma Course Lesson RAG evidence
        course_rag = CourseRAGService.search(message, course_id=course_id, top_k=3)

        reply = ""
        citations = []
        tools_called = []

        msg_lower = message.lower()

        # Check if message is a standard conversational greeting
        greeting_words = {"hello", "hi", "hey", "greetings", "good morning", "good afternoon", "good evening"}
        is_greeting = any(g in msg_lower for g in greeting_words)

        # Deterministic corporate policy & credential guardrails
        if any(w in msg_lower for w in ["promote", "promotion", "guarantee", "salary", "raise"]):
            reply = (
                "Important Disclaimer: Completion of internal courses and external learning paths resolves skill gaps and builds competency, "
                "but does not guarantee formal certification, salary increments, bonuses, or job title promotion. "
                "Proficiency records are updated through verified rubric assessments."
            )
            citations = []
        elif any(w in msg_lower for w in ["budget", "allowance", "reimbursement", "cost"]) and policy_rag.get("evidence_text"):
            reply = (
                f"Based on the official corporate learning policy:\n\n"
                f"{policy_rag['evidence_text']}\n\n"
                f"*Note: Official skill proficiencies are updated exclusively via practical assessments. "
                f"Completing courses does not guarantee promotion or salary increments.*"
            )
            citations = policy_rag.get("citations", [])
            tools_called = [{"tool": "policy_rag_search"}]
        elif any(w in msg_lower for w in ["certificate", "credential", "qualification", "accredited", "badge"]) and not any(w in msg_lower for w in ["python", "code", "syntax", "variable", "lesson", "function", "formula", "excel", "cloud"]):
            reply = (
                "Credential Advisory:\n\n"
                "In our supported course ecosystem, credentials are categorized as follows:\n"
                "1. **Course Completion Certificate**: Confirms attendance/completion of video lessons (e.g. Udemy).\n"
                "2. **Assessed Course Certificate**: Requires passing rigorous weekly graded quizzes or programming assignments (e.g. Coursera Course, edX Verified, freeCodeCamp).\n"
                "3. **Professional Certificate**: A multi-course series featuring capstones and portfolio reviews (e.g. Google Data Analytics, DeepLearning.AI Specializations).\n"
                "4. **Accredited Qualification**: University-partnered programs providing formal academic credit.\n\n"
                "⚠️ *Important Responsible AI Disclaimer: Earning any certificate confirms knowledge acquisition, but does NOT guarantee formal certification passage, promotion, salary increases, or employment outcomes.*"
            )
            citations = []

        # Course-specific question handling: if not found and not a conversational greeting
        elif course_id and not course_rag.get("found") and not is_greeting:
            # Requirement: If relevant content is not found, clearly state answer was not found in course material. Do not fabricate source!
            reply = (
                f"This answer was not found in the course material for {course_title}. "
                f"The lessons in this course focus on verified curriculum topics. "
                f"Please ask a question related to the lessons in {course_title}."
            )
            citations = []
            tools_called = [{"tool": "course_rag_search", "result": "not_found"}]

        else:
            # Query has retrieved relevant course chunks or is general learning question
            retrieved_evidence = course_rag.get("evidence_text", "")
            citations = course_rag.get("citations", [])
            tools_called.append({"tool": "chroma_course_rag", "retrieved_chunks": len(citations)})

            # Call Multi-LLM Provider with Automatic Fallback (Gemini -> OpenAI -> Grok)
            reply, tools_called = cls._call_providers_with_fallback(
                employee_id=employee_id,
                message=message,
                course_context=course_context,
                rag_evidence=retrieved_evidence or policy_rag.get("evidence_text", ""),
                plan_mode=plan_mode,
                history=prior_messages,
                citations=citations
            )

        # Save assistant message
        repository.insert("chat_messages", {
            "message_id": f"MSG-{uuid.uuid4().hex[:8]}",
            "conversation_id": conversation_id,
            "employee_id": employee_id,
            "sender": "assistant",
            "message": reply,
            "course_id": course_id,
            "citations": citations,
            "tools_called": tools_called,
            "created_at": datetime.now(timezone.utc).isoformat()
        })

        return {
            "conversation_id": conversation_id,
            "reply": reply,
            "citations": citations,
            "tools_called": tools_called,
            "course_id": course_id
        }

    @classmethod
    def _call_providers_with_fallback(
        cls,
        employee_id: str,
        message: str,
        course_context: str,
        rag_evidence: str,
        plan_mode: Optional[str],
        history: Optional[List[Dict[str, Any]]] = None,
        citations: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Orchestrates multi-provider execution (Gemini, OpenAI, xAI Grok).
        Honors LLM_PRIMARY_PROVIDER and LLM_FALLBACK_ORDER with automatic failover.
        """
        from app.agent.providers.base import LLMMessage, redact_secrets
        from app.agent.providers.fallback_manager import fallback_manager

        order = settings.get_provider_order()
        api_keys = settings.get_gemini_api_keys()

        # Build normalized LLMMessage history for backup providers
        llm_messages: List[LLMMessage] = []
        if history:
            for pm in history:
                sender = pm.get("sender")
                text = (pm.get("message") or "").strip()
                if not text or text.startswith("AI Advisor Configuration") or text.startswith("AI Service Error"):
                    continue
                role = "user" if sender == "user" else "assistant"
                llm_messages.append(LLMMessage(role=role, content=text))

        context_parts = []
        if course_context:
            context_parts.append(f"--- Active Course Metadata ---\n{course_context.strip()}")
        if rag_evidence:
            context_parts.append(f"--- Retrieved Course Material & Verified Lessons ---\n{rag_evidence.strip()}")

        instruction_suffix = (
            "\n\nRemember to:\n"
            "1. Explain the concept clearly using the retrieved lessons.\n"
            "2. Provide a practical code or formula example with expected output.\n"
            "3. State the exact source reference lesson title.\n"
            "4. Ask one practice question."
        )

        if context_parts:
            current_prompt = "\n\n".join(context_parts) + f"\n\nLearner Question: {message}{instruction_suffix}"
        else:
            current_prompt = message

        llm_messages.append(LLMMessage(role="user", content=current_prompt))

        last_error_msg = ""
        tools_accumulated: List[Dict[str, Any]] = []

        # Check if any provider in order is configured
        has_any_configured = False
        for p_name in order:
            if p_name == "gemini" and api_keys and HAS_GENAI:
                has_any_configured = True
                break
            prov = fallback_manager.get_provider(p_name)
            if prov and prov.is_configured():
                has_any_configured = True
                break

        if not has_any_configured:
            primary = (settings.LLM_PRIMARY_PROVIDER or "gemini").lower()
            if primary == "gemini":
                return (
                    "AI Advisor Configuration Notice: Environment variable 'GEMINI_API_KEY' is missing or not configured. "
                    "Please set 'GEMINI_API_KEY' in your environment or backend/.env file to enable live AI tutor responses.",
                    []
                )
            elif primary == "openai":
                return (
                    "AI Advisor Configuration Notice: Environment variable 'OPENAI_API_KEY' is missing or not configured. "
                    "Please set 'OPENAI_API_KEY' in your environment or backend/.env file to enable live AI responses.",
                    []
                )
            else:
                return (
                    "AI Advisor Configuration Notice: Environment variable 'XAI_API_KEY' is missing or not configured. "
                    "Please set 'XAI_API_KEY' in your environment or backend/.env file to enable live AI responses.",
                    []
                )

        for p_idx, provider_name in enumerate(order):
            if provider_name == "gemini":
                if not api_keys or not HAS_GENAI:
                    continue

                gem_reply, gem_tools = cls._call_gemini_with_fallback(
                    api_keys=api_keys,
                    employee_id=employee_id,
                    message=message,
                    course_context=course_context,
                    rag_evidence=rag_evidence,
                    plan_mode=plan_mode,
                    history=history,
                    citations=citations
                )

                if not gem_reply.startswith("AI Service Error") and not gem_reply.startswith("AI Advisor Configuration"):
                    return gem_reply, gem_tools

                last_error_msg = gem_reply
                tools_accumulated.extend(gem_tools)
                continue

            elif provider_name in ("openai", "grok"):
                backup_provider = fallback_manager.get_provider(provider_name)
                if not backup_provider or not backup_provider.is_configured():
                    continue

                try:
                    res = backup_provider.generate(
                        messages=llm_messages,
                        system_prompt=FULL_SYSTEM_PROMPT,
                        temperature=0.7,
                        timeout=settings.LLM_REQUEST_TIMEOUT
                    )
                    return res.text, res.tools_called
                except Exception as backup_err:
                    clean_err = redact_secrets(str(backup_err))
                    last_error_msg = f"AI Service Error ({provider_name}): {clean_err}"
                    continue

        return last_error_msg or "AI Service Error: All configured LLM providers failed to generate a response.", tools_accumulated

    @classmethod
    def _call_gemini_with_fallback(
        cls,
        api_keys: List[str],
        employee_id: str,
        message: str,
        course_context: str,
        rag_evidence: str,
        plan_mode: Optional[str],
        history: Optional[List[Dict[str, Any]]] = None,
        citations: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Attempts execution across configured Gemini API keys sequentially.
        If a key encounters quota limits (429) or auth errors, seamlessly falls back
        to the next key without exposing any key details or rotation mechanics to the UI.
        """
        last_exception = None

        for idx, key in enumerate(api_keys):
            try:
                reply, tools = cls._execute_gemini_call(
                    api_key=key,
                    employee_id=employee_id,
                    message=message,
                    course_context=course_context,
                    rag_evidence=rag_evidence,
                    plan_mode=plan_mode,
                    history=history,
                    citations=citations
                )
                return reply, tools
            except Exception as e:
                last_exception = e
                if idx < len(api_keys) - 1:
                    # Seamlessly failover to next configured API key without exposing in UI
                    continue
                break

        # All keys failed or non-retriable exception occurred
        err_msg = cls._format_error_message(last_exception, api_keys=api_keys, model_name=settings.GEMINI_MODEL)
        return err_msg, []

    @classmethod
    def _execute_gemini_call(
        cls,
        api_key: str,
        employee_id: str,
        message: str,
        course_context: str,
        rag_evidence: str,
        plan_mode: Optional[str],
        history: Optional[List[Dict[str, Any]]] = None,
        citations: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        client = genai.Client(api_key=api_key)
        active_model = cls.get_verified_model(client, preferred_model=settings.GEMINI_MODEL)

        contents: List[types.Content] = []

        if history:
            for pm in history:
                sender = pm.get("sender")
                text = (pm.get("message") or "").strip()
                if not text:
                    continue
                if text.startswith("AI Advisor Configuration") or text.startswith("AI Service Error"):
                    continue
                role = "user" if sender == "user" else "model"
                contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=text)]
                    )
                )

        context_parts = []
        if course_context:
            context_parts.append(f"--- Active Course Metadata ---\n{course_context.strip()}")
        if rag_evidence:
            context_parts.append(f"--- Retrieved Course Material & Verified Lessons ---\n{rag_evidence.strip()}")

        instruction_suffix = (
            "\n\nRemember to:\n"
            "1. Explain the concept clearly using the retrieved lessons.\n"
            "2. Provide a practical code or formula example with expected output.\n"
            "3. State the exact source reference lesson title.\n"
            "4. Ask one practice question."
        )

        if context_parts:
            current_prompt = "\n\n".join(context_parts) + f"\n\nLearner Question: {message}{instruction_suffix}"
        else:
            current_prompt = message

        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=current_prompt)]
            )
        )

        normalized_contents: List[types.Content] = []
        for c in contents:
            if normalized_contents and normalized_contents[-1].role == c.role:
                normalized_contents[-1].parts.extend(c.parts)
            else:
                normalized_contents.append(c)

        while normalized_contents and normalized_contents[0].role != "user":
            normalized_contents.pop(0)

        if not normalized_contents:
            normalized_contents.append(
                types.Content(role="user", parts=[types.Part.from_text(text=current_prompt)])
            )

        config = types.GenerateContentConfig(
            system_instruction=FULL_SYSTEM_PROMPT,
            temperature=0.7,
        )

        response = client.models.generate_content(
            model=active_model,
            contents=normalized_contents,
            config=config,
        )

        reply = response.text or "I reviewed your question and course curriculum."
        return reply, [{"tool": "gemini_generate", "model": active_model}]

    @classmethod
    def _fallback_response(
        cls,
        employee_id: str,
        message: str,
        course_context: str = "",
        rag_result: Optional[Dict[str, Any]] = None,
        plan_mode: Optional[str] = "self_directed"
    ) -> str:
        """
        Legacy fallback response helper preserved for checklist and unit test resilience verification.
        Note: Normal conversational flow returns transparent service errors rather than generic hints.
        """
        citations_text = ""
        if rag_result and rag_result.get("citations"):
            citations_text = f"\n\nReference Material: {', '.join(rag_result['citations'])}"
        
        topic = "the learning topic"
        if "python" in message.lower() or "python" in course_context.lower():
            topic = "Python"
        elif "excel" in message.lower() or "excel" in course_context.lower():
            topic = "Excel"
        elif "cloud" in message.lower() or "cloud" in course_context.lower():
            topic = "Cloud Computing"

        return (
            f"Hint & Study Guidance for {topic}:\n"
            f"Review the core syntax and structured examples in your course module. "
            f"Focus on breaking down '{message[:50]}' into small, reproducible steps and verify outputs.{citations_text}"
        )
