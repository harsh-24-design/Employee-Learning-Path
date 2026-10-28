import uuid
import hashlib
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timezone

from app.models.schemas import (
    Course,
    SkillGapItem,
    SkillGapAnalysisResponse,
    LearningPlan,
    AssessmentResult,
    LearningProgressItem,
    PlanMode
)
from app.repositories.mongo_repository import repository
from app.agent.engine import LearningPathEngine

def get_employee_skills(employee_id: str) -> Dict[str, int]:
    skills_docs = repository.get_employee_skills(employee_id)
    skills_dict = {}
    for s in skills_docs:
        prof = s.get("verified_level") if s.get("verified_level") is not None else s.get("self_assessed_level", 0)
        skills_dict[s.get("skill", "")] = prof
    return skills_dict

def get_target_competencies(target_role_or_skill: str) -> Tuple[Dict[str, int], bool]:
    """
    Returns (competencies_dict, is_catalog_role).
    If not recognized in catalogue, returns fallback and is_catalog_role=False (Requirement 3).
    """
    role_doc = repository.get_role(target_role_or_skill)
    if role_doc:
        return {c["skill"]: c["required_proficiency"] for c in role_doc.get("competencies", [])}, True
    return {target_role_or_skill: 3}, False

def identify_skill_gaps(employee_id: str, target_role_or_skill: str) -> SkillGapAnalysisResponse:
    current_skills = get_employee_skills(employee_id)
    target_competencies, is_catalog_role = get_target_competencies(target_role_or_skill)
    courses_raw = repository.get_all_courses()
    catalogue = [Course(**c) for c in courses_raw]

    gaps, unfulfillable = LearningPathEngine.calculate_skill_gaps(
        current_skills=current_skills,
        target_competencies=target_competencies,
        catalogue_courses=catalogue
    )

    notes = None if is_catalog_role else f"Role '{target_role_or_skill}' not found in role catalogue. Evaluating as individual skill goal."

    return SkillGapAnalysisResponse(
        employee_id=employee_id,
        target_role=target_role_or_skill,
        gaps=gaps,
        total_gaps=len(gaps),
        unfulfillable_skills=unfulfillable,
        role_competency_available=is_catalog_role,
        notes=notes
    )

def search_courses(
    required_skills: Optional[List[str]] = None,
    max_level: Optional[int] = None,
    max_budget: Optional[float] = None,
    platform: Optional[str] = None,
    certificate_type: Optional[str] = None
) -> List[Course]:
    courses_raw = repository.get_all_courses()
    results = []
    req_skills_lower = [s.lower() for s in (required_skills or [])]

    for c in courses_raw:
        if req_skills_lower and c.get("skill", "").lower() not in req_skills_lower:
            continue
        if max_level is not None and c.get("level", 1) > max_level:
            continue
        if max_budget is not None and c.get("cost", 0.0) > max_budget:
            continue
        if platform and c.get("platform", "Internal").lower() != platform.lower():
            continue
        if certificate_type:
            cert_info = c.get("certificate_info", {})
            if cert_info.get("type") != certificate_type:
                continue
        results.append(Course(**c))
    return results

def generate_learning_plan(
    employee_id: str,
    target_role: Optional[str] = None,
    mode: PlanMode = "self_directed",
    custom_skills: Optional[Dict[str, int]] = None,
    goal_description: Optional[str] = None,
    budget: Optional[float] = 500.0,
    weekly_hours: float = 10.0,
    target_date: Optional[str] = None,
    assigned_by: Optional[str] = None,
    assignment_deadline: Optional[str] = None,
    manager_notes: Optional[str] = None,
    wants_certificate: bool = False,
    preferred_platform: Optional[str] = None,
    training_intensity: str = "normal"
) -> LearningPlan:
    emp = repository.get_employee(employee_id)
    completed_ids = set(emp.get("completed_course_ids", [])) if emp else set()
    current_skills = get_employee_skills(employee_id)

    # Determine target competencies
    is_custom_goal = False
    if custom_skills:
        target_competencies = custom_skills
        is_custom_goal = True
    else:
        target_competencies, _ = get_target_competencies(target_role or "Data Analyst")

    courses_raw = repository.get_all_courses()
    catalogue = [Course(**c) for c in courses_raw]

    return LearningPathEngine.generate_plan(
        employee_id=employee_id,
        target_role=target_role,
        current_skills=current_skills,
        target_competencies=target_competencies,
        catalogue_courses=catalogue,
        completed_course_ids=completed_ids,
        weekly_hours=weekly_hours,
        budget=budget,
        mode=mode,
        is_custom_goal=is_custom_goal,
        goal_description=goal_description,
        assigned_by=assigned_by,
        assignment_deadline=assignment_deadline,
        manager_notes=manager_notes,
        wants_certificate=wants_certificate,
        preferred_platform=preferred_platform,
        training_intensity=training_intensity,
        target_date=target_date
    )

def save_learning_plan(employee_id: str, plan: LearningPlan) -> LearningPlan:
    # Check existing plan matching same mode
    plans = repository.find("learning_plans", {"employee_id": employee_id, "mode": plan.mode})
    if plans:
        plans.sort(key=lambda x: x.get("version", 1), reverse=True)
        active = plans[0]
        if active.get("content_hash") == plan.content_hash:
            return LearningPlan(**active)

    plan_dict = plan.model_dump()
    repository.save_plan(plan_dict)
    return plan

def get_employee_plan_history(employee_id: str) -> List[LearningPlan]:
    plans = repository.find("learning_plans", {"employee_id": employee_id})
    plans.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return [LearningPlan(**p) for p in plans]

def get_team_members_summary() -> List[Dict[str, Any]]:
    employees = repository.find("employees")
    team = []
    for emp in employees:
        emp_id = emp.get("employee_id")
        assigned_plan = get_active_plan_for_mode(emp_id, "company_assigned")

        progress_pct = 0.0
        if assigned_plan and assigned_plan.ordered_courses:
            completed_set = set(emp.get("completed_course_ids", []))
            done = sum(1 for c in assigned_plan.ordered_courses if c.course_id in completed_set)
            progress_pct = round((done / len(assigned_plan.ordered_courses)) * 100, 1)

        user_doc = repository.find_one("users", {"employee_id": emp_id})
        email = user_doc.get("email") if user_doc else f"{emp_id.lower()}@company.internal"

        team.append({
            "employee_id": emp_id,
            "name": emp.get("name", f"Employee {emp_id}"),
            "department": emp.get("department", "Engineering"),
            "email": email,
            "has_active_assigned_plan": assigned_plan is not None,
            "assigned_role": assigned_plan.target_role if assigned_plan else None,
            "assigned_deadline": assigned_plan.assignment_deadline if assigned_plan else None,
            "assigned_progress_percent": progress_pct,
            "completed_courses_count": len(emp.get("completed_course_ids", []))
        })
    return team

def get_active_plan_for_mode(employee_id: str, mode: PlanMode = "self_directed") -> Optional[LearningPlan]:
    plans = repository.find("learning_plans", {"employee_id": employee_id, "mode": mode})
    if plans:
        plans.sort(key=lambda x: x.get("version", 1), reverse=True)
        return LearningPlan(**plans[0])
    return None

def update_learning_plan(
    employee_id: str,
    weekly_hours: Optional[float] = None,
    budget: Optional[float] = None,
    target_date: Optional[str] = None,
    mode: PlanMode = "self_directed"
) -> Optional[LearningPlan]:
    current_plan = get_active_plan_for_mode(employee_id, mode)
    if not current_plan:
        return None

    new_hours = weekly_hours if weekly_hours is not None else current_plan.weekly_hours
    new_budget = budget if budget is not None else current_plan.budget_limit

    new_plan = generate_learning_plan(
        employee_id=employee_id,
        target_role=current_plan.target_role,
        mode=mode,
        custom_skills=current_plan.target_competencies if current_plan.is_custom_goal else None,
        goal_description=current_plan.goal_description,
        budget=new_budget,
        weekly_hours=new_hours,
        target_date=target_date,
        assigned_by=current_plan.assigned_by,
        assignment_deadline=current_plan.assignment_deadline,
        manager_notes=current_plan.manager_notes
    )
    new_plan.version = current_plan.version + 1
    new_plan.updated_at = datetime.now(timezone.utc).isoformat()
    
    repository.save_plan(new_plan.model_dump())
    return new_plan

def record_lesson_progress(
    employee_id: str,
    course_id: str,
    lesson_id: str,
    status: str = "completed",
    time_spent_minutes: int = 30
) -> LearningProgressItem:
    progress_query = {
        "employee_id": employee_id,
        "course_id": course_id,
        "lesson_id": lesson_id
    }
    existing = repository.find_one("learning_progress", progress_query)
    now_str = datetime.now(timezone.utc).isoformat()

    if existing:
        update_data = {
            "status": status,
            "time_spent_minutes": existing.get("time_spent_minutes", 0) + time_spent_minutes,
            "updated_at": now_str
        }
        if status == "completed" and not existing.get("completed_at"):
            update_data["completed_at"] = now_str
        repository.update("learning_progress", progress_query, update_data)
        updated_doc = repository.find_one("learning_progress", progress_query)
        return LearningProgressItem(
            progress_id=str(updated_doc.get("_id", lesson_id)),
            employee_id=employee_id,
            course_id=course_id,
            lesson_id=lesson_id,
            status=updated_doc["status"],
            time_spent_minutes=updated_doc["time_spent_minutes"],
            completed_at=updated_doc.get("completed_at"),
            updated_at=updated_doc["updated_at"]
        )

    prog_id = f"PROG-{uuid.uuid4().hex[:8]}"
    doc = {
        "progress_id": prog_id,
        "employee_id": employee_id,
        "course_id": course_id,
        "lesson_id": lesson_id,
        "status": status,
        "time_spent_minutes": time_spent_minutes,
        "completed_at": now_str if status == "completed" else None,
        "created_at": now_str,
        "updated_at": now_str
    }
    repository.insert("learning_progress", doc)
    return LearningProgressItem(
        progress_id=prog_id,
        employee_id=employee_id,
        course_id=course_id,
        lesson_id=lesson_id,
        status=status,
        time_spent_minutes=time_spent_minutes,
        completed_at=doc["completed_at"],
        updated_at=now_str
    )

def record_assessment_result(
    employee_id: str,
    course_id: str,
    assessment_id: str,
    score: int,
    evidence: str,
    skill_id: str,
    target_level: int,
    passing_score: int = 70
) -> AssessmentResult:
    passed = (score >= passing_score)
    now_str = datetime.now(timezone.utc).isoformat()
    
    doc = {
        "assessment_id": assessment_id,
        "employee_id": employee_id,
        "course_id": course_id,
        "skill_id": skill_id,
        "score": score,
        "max_score": 100,
        "passed": passed,
        "rubric_version": "v1.0-standardized",
        "evidence": evidence,
        "created_at": now_str
    }
    repository.insert("assessments", doc)

    updated_prof = None
    if passed:
        updated_prof = recalculate_proficiency(employee_id, skill_id, target_level)

    return AssessmentResult(
        assessment_id=assessment_id,
        employee_id=employee_id,
        course_id=course_id,
        skill_id=skill_id,
        score=score,
        max_score=100,
        passed=passed,
        rubric_version="v1.0-standardized",
        evidence=evidence,
        updated_verified_level=updated_prof,
        created_at=now_str
    )

def recalculate_proficiency(employee_id: str, skill_id: str, new_level: int) -> int:
    current_skills = repository.get_employee_skills(employee_id)
    existing_prof = 0
    for s in current_skills:
        if s.get("skill", "").lower() == skill_id.lower():
            existing_prof = s.get("verified_level") or s.get("self_assessed_level", 0)
            break

    final_level = max(existing_prof, new_level)
    repository.update_employee_skill(
        employee_id=employee_id,
        skill=skill_id,
        verified_level=final_level,
        source="standardized_assessment"
    )
    return final_level

def answer_learning_question(
    employee_id: str,
    course_id: Optional[str],
    message: str,
    conversation_id: Optional[str] = None,
    plan_mode: Optional[str] = "self_directed"
) -> Dict[str, Any]:
    from app.agent.gemini_advisor import GeminiAdvisor
    return GeminiAdvisor.chat(
        employee_id=employee_id,
        course_id=course_id,
        message=message,
        conversation_id=conversation_id,
        plan_mode=plan_mode
    )
