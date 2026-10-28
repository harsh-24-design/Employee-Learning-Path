import os
import uuid
import json
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Header, Path, Security, Depends, status
from fastapi.security import HTTPAuthorizationCredentials
from datetime import datetime, timezone

from app.models.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    UserProfile,
    AuthTokenResponse,
    LogoutResponse,
    CustomGoalRequest,
    CompanyGoalAssignmentRequest,
    TeamMemberSummary,
    RoleCreateUpdateRequest,
    EmployeeProfile,
    EmployeeProfileUpdateRequest,
    EmployeeSkill,
    Role,
    Course,
    SkillGapAnalysisRequest,
    SkillGapAnalysisResponse,
    PlanGenerationRequest,
    PlanUpdateRequest,
    LearningPlan,
    ProgressRecordRequest,
    LearningProgressItem,
    AssessmentSubmissionRequest,
    AssessmentResult,
    ChatConversationCreateRequest,
    ChatConversation,
    ChatMessageSendRequest,
    ChatResponse,
    ChatMessage,
    DashboardResponse,
    DashboardActivity,
    CourseQuiz
)
from app.repositories.mongo_repository import repository
from app.core.config import settings
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    revoke_token,
    verify_user_access,
    require_role,
    security_bearer
)
from app.agent.tools import (
    get_employee_skills,
    get_target_competencies,
    identify_skill_gaps,
    search_courses,
    generate_learning_plan,
    save_learning_plan,
    record_lesson_progress,
    record_assessment_result,
    update_learning_plan,
    answer_learning_question,
    get_active_plan_for_mode,
    get_employee_plan_history,
    get_team_members_summary
)
from app.services.ingestion import DataIngestionService

router = APIRouter()

DEFAULT_EMP_ID = "E2001"

def resolve_effective_emp_id(
    current_user: Any,
    x_employee_id: Optional[str] = None,
    requested_id: Optional[str] = None
) -> str:
    """
    Derives employee ID securely:
    - If authenticated, derives from current_user and verifies access if another ID is requested.
    - If unauthenticated, allows x_employee_id only if provided (e.g. legacy/test calls), else raises 401.
    """
    user = current_user if isinstance(current_user, UserProfile) else None
    if user:
        owner_id = user.employee_id or user.user_id
        target = requested_id or x_employee_id
        if target and target != owner_id:
            verify_user_access(user, target)
            return target
        return owner_id
    if x_employee_id:
        return x_employee_id
    if requested_id:
        return requested_id
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials were not provided."
    )

@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Employee Learning Path Advisory Agent",
        "database_mode": "MongoDB" if repository.use_mongo else "Local Memory/File Fallback",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# --- 0. Authentication & User Management (Requirement 1, 2, 3 & 10) ---
@router.post("/auth/register", response_model=AuthTokenResponse)
def register_user(req: UserRegisterRequest):
    email_clean = req.email.strip().lower()
    if not email_clean or "@" not in email_clean:
        raise HTTPException(status_code=400, detail="Invalid email address format.")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    if len(req.name.strip()) < 2:
        raise HTTPException(status_code=400, detail="Name must be at least 2 characters.")

    existing = repository.find_one("users", {"email": email_clean})
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists.")

    user_id = f"USR-{uuid.uuid4().hex[:8].upper()}"
    emp_id = req.employee_id.strip() if req.employee_id else None

    # If independent learner without employee ID, assign a learner profile ID
    if not emp_id:
        if req.is_employee:
            emp_id = f"EMP-{uuid.uuid4().hex[:6].upper()}"
        else:
            emp_id = f"LRN-{uuid.uuid4().hex[:6].upper()}"

    # Security requirement: New users must NEVER be automatically granted Admin permissions
    assigned_role = "learner"
    if req.role in ["learner", "manager"]:
        assigned_role = req.role

    user_doc = {
        "user_id": user_id,
        "email": email_clean,
        "password_hash": hash_password(req.password),
        "name": req.name.strip(),
        "role": assigned_role,
        "is_employee": req.is_employee,
        "employee_id": emp_id,
        "department": req.department or ("Corporate Employee" if req.is_employee else "Independent Learner"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    repository.insert("users", user_doc)

    # Empty profile initialization for fresh onboarding flow (no fake prefilled roles or goals)
    if not repository.get_employee(emp_id):
        repository.insert("employees", {
            "employee_id": emp_id,
            "user_id": user_id,
            "name": req.name.strip(),
            "department": user_doc["department"],
            "target_role": "",  # Empty for real onboarding!
            "preferences": {
                "preferred_learning_style": "mixed",
                "daily_study_hours": 1.5,
                "weekly_hours_available": 10.0,
                "training_intensity": "normal",
                "budget_limit": 500.0 if req.is_employee else 200.0,
                "target_completion_date": None,
                "wants_certificate": False,
                "preferred_certificate_type": None,
                "preferred_platforms": []
            },
            "completed_course_ids": []
        })

    token = create_access_token(user_id=user_id, email=user_doc["email"], role=assigned_role, employee_id=emp_id)
    profile = UserProfile(
        user_id=user_id,
        email=user_doc["email"],
        name=user_doc["name"],
        role=user_doc["role"],
        is_employee=user_doc["is_employee"],
        employee_id=emp_id,
        department=user_doc["department"],
        created_at=user_doc["created_at"]
    )
    return AuthTokenResponse(token=token, user=profile, message="Registration successful.")

@router.post("/auth/login", response_model=AuthTokenResponse)
def login_user(req: UserLoginRequest):
    email_clean = req.email.strip().lower()
    user_doc = repository.find_one("users", {"email": email_clean})
    if not user_doc or not verify_password(req.password, user_doc.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    emp_id = user_doc.get("employee_id")
    token = create_access_token(
        user_id=user_doc["user_id"],
        email=user_doc["email"],
        role=user_doc.get("role", "learner"),
        employee_id=emp_id
    )
    profile = UserProfile(
        user_id=user_doc["user_id"],
        email=user_doc["email"],
        name=user_doc.get("name", "User"),
        role=user_doc.get("role", "learner"),
        is_employee=user_doc.get("is_employee", False),
        employee_id=emp_id,
        department=user_doc.get("department", "Independent Learning"),
        created_at=user_doc.get("created_at")
    )
    return AuthTokenResponse(token=token, user=profile, message="Login successful.")

@router.get("/auth/me", response_model=UserProfile)
def get_authenticated_user_profile(current_user: UserProfile = Depends(get_current_user)):
    return current_user

@router.post("/auth/logout", response_model=LogoutResponse)
def logout_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)):
    if credentials and credentials.credentials:
        revoke_token(credentials.credentials)
    return LogoutResponse(message="Logged out successfully.")

@router.get("/auth/users", response_model=List[UserProfile])
def list_demo_users():
    raw_users = repository.find("users")
    profiles = []
    for u in raw_users:
        profiles.append(UserProfile(
            user_id=u["user_id"],
            email=u["email"],
            name=u.get("name", "User"),
            role=u.get("role", "learner"),
            is_employee=u.get("is_employee", False),
            employee_id=u.get("employee_id"),
            department=u.get("department", "Independent Learning"),
            created_at=u.get("created_at")
        ))
    return profiles

# --- 1. Employee Profile (Section 5.2) ---
@router.get("/employees/me", response_model=EmployeeProfile)
def get_current_employee_profile(
    current_user: Optional[UserProfile] = Depends(get_current_user),
    x_employee_id: Optional[str] = Header(None)
):
    emp_id = resolve_effective_emp_id(current_user, x_employee_id=x_employee_id)
    emp = repository.get_employee(emp_id)
    if not emp:
        emp = {
            "employee_id": emp_id,
            "name": current_user.name if current_user else f"Learner {emp_id}",
            "department": current_user.department if current_user else "Independent Learning",
            "target_role": "",  # Empty for unassigned/new learner
            "preferences": {
                "preferred_learning_style": "mixed",
                "daily_study_hours": 1.5,
                "weekly_hours_available": 10.0,
                "training_intensity": "normal",
                "budget_limit": 500.0,
                "target_completion_date": None
            },
            "completed_course_ids": []
        }
        repository.insert("employees", emp)

    skills_raw = repository.get_employee_skills(emp_id)
    skills = []
    for s in skills_raw:
        skills.append(EmployeeSkill(
            skill_id=s.get("skill", ""),
            skill=s.get("skill", ""),
            self_assessed_level=s.get("self_assessed_level", 0),
            verified_level=s.get("verified_level"),
            assessment_source=s.get("assessment_source", "self"),
            updated_at=s.get("updated_at")
        ))

    return EmployeeProfile(
        employee_id=emp["employee_id"],
        employee_code=emp.get("employee_code", emp_id),
        name=emp.get("name", "Employee"),
        department=emp.get("department", "Engineering"),
        target_role=emp.get("target_role", ""),
        preferences=emp.get("preferences", {}),
        skills=skills,
        completed_course_ids=emp.get("completed_course_ids", []),
        created_at=emp.get("created_at"),
        updated_at=emp.get("updated_at")
    )

@router.put("/employees/me", response_model=EmployeeProfile)
def update_current_employee_profile(
    req: EmployeeProfileUpdateRequest,
    current_user: Optional[UserProfile] = Depends(get_current_user),
    x_employee_id: Optional[str] = Header(None)
):
    emp_id = resolve_effective_emp_id(current_user, x_employee_id=x_employee_id)
    emp = repository.get_employee(emp_id) or {"employee_id": emp_id}

    update_data: Dict[str, Any] = {}
    if req.name is not None:
        update_data["name"] = req.name
    if req.department is not None:
        update_data["department"] = req.department
    if req.target_role is not None:
        update_data["target_role"] = req.target_role
    if req.preferences is not None:
        update_data["preferences"] = req.preferences.model_dump()

    if update_data:
        repository.update("employees", {"employee_id": emp_id}, update_data, upsert=True)

    # If self-assessed skills were updated
    if req.self_assessed_skills:
        for skill_name, rating in req.self_assessed_skills.items():
            if 0 <= rating <= 5:
                repository.update_employee_skill(
                    employee_id=emp_id,
                    skill=skill_name,
                    self_level=rating,
                    source="self_assessment"
                )

    return get_current_employee_profile(current_user=current_user, x_employee_id=emp_id)

# --- 2. Skills & Roles ---
@router.get("/skills")
def list_skills():
    courses = repository.get_all_courses()
    skills_set = sorted(list({c.get("skill") for c in courses if c.get("skill")}))
    return [{"skill_id": s, "name": s} for s in skills_set]

@router.get("/roles", response_model=List[Role])
def list_roles():
    roles_raw = repository.get_all_roles()
    return [Role(**r) for r in roles_raw]

@router.post("/roles", response_model=Role)
def create_role(
    req: RoleCreateUpdateRequest,
    current_user: Optional[UserProfile] = Depends(get_current_user)
):
    if isinstance(current_user, UserProfile) and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden: administrator role required.")
    existing = repository.get_role(req.role_name)
    if existing:
        raise HTTPException(status_code=400, detail=f"Role '{req.role_name}' already exists.")
    role_doc = req.model_dump()
    repository.insert("roles", role_doc)
    return Role(**role_doc)

@router.put("/roles/{role_name}", response_model=Role)
def update_role(
    role_name: str,
    req: RoleCreateUpdateRequest,
    current_user: Optional[UserProfile] = Depends(get_current_user)
):
    if isinstance(current_user, UserProfile) and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden: administrator role required.")
    existing = repository.get_role(role_name)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Role '{role_name}' not found.")
    role_doc = req.model_dump()
    repository.update("roles", {"role_name": role_name}, role_doc)
    return Role(**role_doc)

# --- 3. Courses Catalogue & Multi-Platform Discovery (Requirement 4) ---
@router.get("/courses", response_model=List[Course])
def list_courses(
    skill: Optional[str] = Query(None),
    max_cost: Optional[float] = Query(None),
    max_level: Optional[int] = Query(None)
):
    return search_courses(
        required_skills=[skill] if skill else None,
        max_level=max_level,
        max_budget=max_cost
    )

@router.get("/courses/discover", response_model=List[Course])
def discover_courses(
    query: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    skill: Optional[str] = Query(None),
    pricing_model: Optional[str] = Query(None),
    certificate_type: Optional[str] = Query(None),
    verification_status: Optional[str] = Query(None),
    max_budget: Optional[float] = Query(None)
):
    # Normalize parameters if invoked directly in python
    q_str = query.strip() if isinstance(query, str) else None
    plat_str = platform.strip() if isinstance(platform, str) else None
    skill_str = skill.strip() if isinstance(skill, str) else None
    pm_str = pricing_model.strip() if isinstance(pricing_model, str) else None
    cert_str = certificate_type.strip() if isinstance(certificate_type, str) else None
    ver_str = verification_status.strip() if isinstance(verification_status, str) else None
    budget_val = max_budget if isinstance(max_budget, (int, float)) else None

    courses_raw = repository.get_all_courses()
    results = []
    for c in courses_raw:
        if q_str:
            q_lower = q_str.lower()
            if q_lower not in c.get("title", "").lower() and q_lower not in c.get("skill", "").lower() and q_lower not in c.get("provider", "").lower():
                continue
        if plat_str and plat_str.lower() != "all" and c.get("platform", "").lower() != plat_str.lower():
            continue
        if skill_str and c.get("skill", "").lower() != skill_str.lower():
            continue
        if pm_str and c.get("pricing_model", "").lower() != pm_str.lower():
            continue
        if cert_str:
            cert_info = c.get("certificate_info", {})
            if cert_info.get("type") != cert_str:
                continue
        if ver_str and c.get("source_verification_status", "").lower() != ver_str.lower():
            continue
        if budget_val is not None and c.get("cost", 0.0) > budget_val:
            continue
        results.append(Course(**c))
    return results

@router.get("/courses/{course_id}", response_model=Course)
def get_course_detail(course_id: str = Path(...)):
    c = repository.get_course(course_id)
    if not c:
        raise HTTPException(status_code=404, detail=f"Course {course_id} not found in catalogue.")
    # Enrich with modules, rich lessons, and demo metadata from lessons_and_quizzes.json
    quiz_file = os.path.join(settings.DATA_DIR, "lessons_and_quizzes.json")
    if os.path.exists(quiz_file):
        try:
            with open(quiz_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if course_id in data:
                    c_extra = data[course_id]
                    if "modules" in c_extra:
                        c["modules"] = c_extra["modules"]
                    if "lessons" in c_extra:
                        c["lessons"] = c_extra["lessons"]
                    if "quiz" in c_extra:
                        c["quiz"] = c_extra["quiz"]
                    if "demo_disclaimer" in c_extra:
                        c["demo_disclaimer"] = c_extra["demo_disclaimer"]
                        c["is_demo"] = True
        except Exception:
            pass
    return Course(**c)

@router.get("/courses/{course_id}/quiz")
def get_course_quiz(
    course_id: str = Path(...),
    module_id: Optional[str] = Query(None)
):
    quiz_file = os.path.join(settings.DATA_DIR, "lessons_and_quizzes.json")
    if os.path.exists(quiz_file):
        try:
            with open(quiz_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if course_id in data:
                    cdata = data[course_id]
                    if module_id and "modules" in cdata:
                        for m in cdata["modules"]:
                            if m.get("module_id") == module_id and "quiz" in m:
                                return m["quiz"]
                    if "quiz" in cdata:
                        return cdata["quiz"]
                    if "modules" in cdata and cdata["modules"] and "quiz" in cdata["modules"][0]:
                        return cdata["modules"][0]["quiz"]
        except Exception:
            pass
    course = repository.get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    return {
        "assessment_id": f"QZ-{course_id}",
        "skill_id": course.get("skill", "General"),
        "level": course.get("level", 1),
        "max_score": 100,
        "passing_score": 70,
        "rubric": f"Score >= 70 demonstrates verified proficiency level {course.get('level', 1)}.",
        "questions": [
            {
                "question_id": "q1",
                "prompt": f"What is the primary objective when studying {course.get('title')}?",
                "options": [
                    "To understand foundational syntax and applied concepts",
                    "To bypass standard best practices",
                    "To memorize syntax without practical execution"
                ],
                "correct_option_index": 0
            },
            {
                "question_id": "q2",
                "prompt": f"Which pattern represents the recommended implementation in {course.get('skill')}?",
                "options": [
                    "Modular, well-structured, and verified logic",
                    "Monolithic untracked script",
                    "Arbitrary unvalidated queries"
                ],
                "correct_option_index": 0
            }
        ]
    }

# --- 4. Skill Gap Analysis (FR-02) ---
@router.post("/skill-gaps/analyze", response_model=SkillGapAnalysisResponse)
def analyze_skill_gaps(
    req: SkillGapAnalysisRequest,
    current_user: Optional[UserProfile] = Depends(get_current_user)
):
    emp_id = resolve_effective_emp_id(current_user, requested_id=req.employee_id)
    return identify_skill_gaps(emp_id, req.target_role)

# --- 5. Learning Plans / Roadmap (FR-04, FR-05, Requirements 2 & 7) ---
@router.post("/learning-plans/generate", response_model=LearningPlan)
def generate_roadmap(
    req: PlanGenerationRequest,
    current_user: Optional[UserProfile] = Depends(get_current_user)
):
    emp_id = resolve_effective_emp_id(current_user, requested_id=req.employee_id)
    plan = generate_learning_plan(
        employee_id=emp_id,
        target_role=req.target_role,
        mode=req.mode,
        custom_skills=req.custom_skills,
        goal_description=req.goal_description,
        budget=req.budget,
        weekly_hours=req.weekly_hours or 10.0,
        target_date=req.target_date,
        wants_certificate=req.wants_certificate,
        preferred_platform=req.preferred_platform,
        training_intensity=req.training_intensity or "normal"
    )
    saved = save_learning_plan(emp_id, plan)
    return saved

@router.get("/learning-plans/self-directed", response_model=Optional[LearningPlan])
def get_self_directed_plan(
    current_user: Optional[UserProfile] = Depends(get_current_user),
    x_employee_id: Optional[str] = Header(None)
):
    emp_id = resolve_effective_emp_id(current_user, x_employee_id=x_employee_id)
    return get_active_plan_for_mode(emp_id, "self_directed")

@router.get("/learning-plans/company-assigned", response_model=Optional[LearningPlan])
def get_company_assigned_plan(
    current_user: Optional[UserProfile] = Depends(get_current_user),
    x_employee_id: Optional[str] = Header(None)
):
    emp_id = resolve_effective_emp_id(current_user, x_employee_id=x_employee_id)
    return get_active_plan_for_mode(emp_id, "company_assigned")

@router.post("/learning-plans/custom-goal", response_model=LearningPlan)
def create_custom_learning_goal(
    req: CustomGoalRequest,
    current_user: Optional[UserProfile] = Depends(get_current_user),
    x_employee_id: Optional[str] = Header(None)
):
    emp_id = resolve_effective_emp_id(current_user, x_employee_id=x_employee_id, requested_id=req.employee_id)
    plan = generate_learning_plan(
        employee_id=emp_id,
        target_role=req.goal_title,
        mode="self_directed",
        custom_skills=req.target_skills,
        goal_description=req.goal_description,
        budget=req.budget,
        weekly_hours=req.weekly_hours or 10.0
    )
    saved = save_learning_plan(emp_id, plan)
    return saved

@router.post("/learning-plans/assign-company-goal", response_model=LearningPlan)
def assign_company_learning_goal(
    req: CompanyGoalAssignmentRequest,
    current_user: Optional[UserProfile] = Depends(get_current_user),
    x_employee_id: Optional[str] = Header(None)
):
    user = current_user if isinstance(current_user, UserProfile) else None
    if user and user.role not in ["manager", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: only managers and administrators can assign company goals."
        )
    manager_id = (user.employee_id or user.user_id) if user else (x_employee_id or "M1001")
    plan = generate_learning_plan(
        employee_id=req.employee_id,
        target_role=req.target_role,
        mode="company_assigned",
        budget=req.budget,
        weekly_hours=req.weekly_hours,
        assigned_by=manager_id,
        assignment_deadline=req.assignment_deadline,
        manager_notes=req.manager_notes
    )
    saved = save_learning_plan(req.employee_id, plan)
    return saved

@router.get("/learning-plans/history", response_model=List[LearningPlan])
def get_plan_history(
    current_user: Optional[UserProfile] = Depends(get_current_user),
    x_employee_id: Optional[str] = Header(None)
):
    emp_id = resolve_effective_emp_id(current_user, x_employee_id=x_employee_id)
    return get_employee_plan_history(emp_id)

@router.get("/learning-plans/current", response_model=Optional[LearningPlan])
def get_current_plan(
    current_user: Optional[UserProfile] = Depends(get_current_user),
    x_employee_id: Optional[str] = Header(None)
):
    emp_id = resolve_effective_emp_id(current_user, x_employee_id=x_employee_id)
    plan_dict = repository.get_active_plan(emp_id)
    if not plan_dict:
        return None
    return LearningPlan(**plan_dict)

@router.put("/learning-plans/current", response_model=LearningPlan)
def update_current_plan(
    req: PlanUpdateRequest,
    current_user: Optional[UserProfile] = Depends(get_current_user),
    x_employee_id: Optional[str] = Header(None)
):
    emp_id = resolve_effective_emp_id(current_user, x_employee_id=x_employee_id)
    updated = update_learning_plan(
        employee_id=emp_id,
        weekly_hours=req.weekly_hours,
        budget=req.budget,
        target_date=req.target_date
    )
    if not updated:
        raise HTTPException(status_code=404, detail="No active plan found to update.")
    return updated

# --- 6. Progress Tracking (FR-06, Section 5.4) ---
@router.patch("/learning-progress/{progress_id}", response_model=LearningProgressItem)
def update_progress_by_id(
    progress_id: str,
    req: ProgressRecordRequest,
    current_user: Optional[UserProfile] = Depends(get_current_user),
    x_employee_id: Optional[str] = Header(None)
):
    emp_id = resolve_effective_emp_id(current_user, x_employee_id=x_employee_id, requested_id=req.employee_id)
    return record_lesson_progress(
        employee_id=emp_id,
        course_id=req.course_id,
        lesson_id=req.lesson_id,
        status=req.status,
        time_spent_minutes=req.time_spent_minutes
    )

@router.post("/learning-progress", response_model=LearningProgressItem)
def create_or_update_progress(
    req: ProgressRecordRequest,
    current_user: Optional[UserProfile] = Depends(get_current_user),
    x_employee_id: Optional[str] = Header(None)
):
    emp_id = resolve_effective_emp_id(current_user, x_employee_id=x_employee_id, requested_id=req.employee_id)
    return record_lesson_progress(
        employee_id=emp_id,
        course_id=req.course_id,
        lesson_id=req.lesson_id,
        status=req.status,
        time_spent_minutes=req.time_spent_minutes
    )

@router.get("/learning-progress", response_model=List[LearningProgressItem])
def get_employee_progress(
    course_id: Optional[str] = Query(None),
    current_user: Optional[UserProfile] = Depends(get_current_user),
    x_employee_id: Optional[str] = Header(None)
):
    emp_id = resolve_effective_emp_id(current_user, x_employee_id=x_employee_id)
    raw = repository.get_learning_progress(emp_id, course_id=course_id)
    items = []
    for r in raw:
        items.append(LearningProgressItem(
            progress_id=r.get("progress_id", str(r.get("_id", ""))),
            employee_id=r.get("employee_id", emp_id),
            plan_id=r.get("plan_id"),
            course_id=r.get("course_id", ""),
            lesson_id=r.get("lesson_id", ""),
            status=r.get("status", "in_progress"),
            time_spent_minutes=r.get("time_spent_minutes", 0),
            completed_at=r.get("completed_at"),
            updated_at=r.get("updated_at", "")
        ))
    return items

# --- 7. Assessments & Proficiency Updates (FR-07, Section 5.5) ---
@router.post("/assessments", response_model=AssessmentResult)
def submit_assessment(
    req: AssessmentSubmissionRequest,
    current_user: Optional[UserProfile] = Depends(get_current_user),
    x_employee_id: Optional[str] = Header(None)
):
    emp_id = resolve_effective_emp_id(current_user, x_employee_id=x_employee_id, requested_id=req.employee_id)
    
    # Locate exact matching quiz (module or course level)
    quiz_data = None
    quiz_file = os.path.join(settings.DATA_DIR, "lessons_and_quizzes.json")
    if os.path.exists(quiz_file):
        try:
            with open(quiz_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if req.course_id in data:
                    cdata = data[req.course_id]
                    for m in cdata.get("modules", []):
                        if m.get("quiz", {}).get("assessment_id") == req.assessment_id:
                            quiz_data = m["quiz"]
                            break
                    if not quiz_data and cdata.get("quiz", {}).get("assessment_id") == req.assessment_id:
                        quiz_data = cdata["quiz"]
        except Exception:
            pass

    if not quiz_data:
        quiz_data = get_course_quiz(req.course_id)

    questions = quiz_data.get("questions", [])
    skill_id = quiz_data.get("skill_id", "General")
    target_level = quiz_data.get("level", 1)
    passing_score = quiz_data.get("passing_score", 70)

    # Score answers
    correct_count = 0
    total = len(questions)
    for q in questions:
        qid = q.get("question_id")
        expected = q.get("correct_option_index")
        if req.answers.get(qid) == expected:
            correct_count += 1

    score = int((correct_count / total * 100)) if total > 0 else 100
    evidence = (
        f"Answered {correct_count}/{total} questions correctly ({score}%). "
        f"Rubric: {quiz_data.get('rubric', '')}"
    )

    return record_assessment_result(
        employee_id=emp_id,
        course_id=req.course_id,
        assessment_id=req.assessment_id,
        score=score,
        evidence=evidence,
        skill_id=skill_id,
        target_level=target_level,
        passing_score=passing_score
    )

@router.get("/assessments", response_model=List[AssessmentResult])
def get_assessments_history(
    current_user: Optional[UserProfile] = Depends(get_current_user),
    x_employee_id: Optional[str] = Header(None)
):
    emp_id = resolve_effective_emp_id(current_user, x_employee_id=x_employee_id)
    raw = repository.get_assessments(emp_id)
    results = []
    for r in raw:
        results.append(AssessmentResult(
            assessment_id=r.get("assessment_id", ""),
            employee_id=r.get("employee_id", emp_id),
            course_id=r.get("course_id", ""),
            skill_id=r.get("skill_id", ""),
            score=r.get("score", 0),
            max_score=r.get("max_score", 100),
            passed=r.get("passed", False),
            rubric_version=r.get("rubric_version", "v1.0"),
            evidence=r.get("evidence", ""),
            created_at=r.get("created_at", "")
        ))
    return results

# --- 8. AI Chatbot (FR-08, Section 5.6) ---
@router.post("/chat/conversations", response_model=ChatConversation)
def create_chat_conversation(
    req: ChatConversationCreateRequest,
    current_user: Optional[UserProfile] = Depends(get_current_user),
    x_employee_id: Optional[str] = Header(None)
):
    emp_id = resolve_effective_emp_id(current_user, x_employee_id=x_employee_id, requested_id=req.employee_id)
    now_str = datetime.now(timezone.utc).isoformat()
    conv_id = f"CONV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    doc = {
        "conversation_id": conv_id,
        "employee_id": emp_id,
        "course_id": req.course_id,
        "title": f"Doubt Resolution: {req.course_id or 'General'}",
        "created_at": now_str,
        "updated_at": now_str
    }
    saved = repository.insert("chat_conversations", doc)
    return ChatConversation(**saved)

@router.get("/chat/conversations", response_model=List[ChatConversation])
def list_chat_conversations(
    current_user: Optional[UserProfile] = Depends(get_current_user),
    x_employee_id: Optional[str] = Header(None)
):
    emp_id = resolve_effective_emp_id(current_user, x_employee_id=x_employee_id)
    raw = repository.get_chat_conversations(emp_id)
    return [ChatConversation(**r) for r in raw]

@router.post("/chat/conversations/{conversation_id}/messages", response_model=ChatResponse)
def send_chat_message(
    conversation_id: str,
    req: ChatMessageSendRequest,
    current_user: Optional[UserProfile] = Depends(get_current_user),
    x_employee_id: Optional[str] = Header(None)
):
    emp_id = resolve_effective_emp_id(current_user, x_employee_id=x_employee_id, requested_id=req.employee_id)
    res = answer_learning_question(
        employee_id=emp_id,
        course_id=req.course_id,
        message=req.message,
        conversation_id=conversation_id,
        plan_mode=req.plan_mode
    )
    return ChatResponse(
        conversation_id=res["conversation_id"],
        reply=res["reply"],
        citations=res.get("citations", []),
        tools_called=res.get("tools_called", []),
        course_id=res.get("course_id")
    )

@router.get("/chat/conversations/{conversation_id}/messages", response_model=List[ChatMessage])
def get_conversation_history(conversation_id: str):
    raw = repository.get_chat_messages(conversation_id)
    results = []
    for m in raw:
        results.append(ChatMessage(
            message_id=m.get("message_id", str(m.get("_id", ""))),
            conversation_id=m.get("conversation_id", conversation_id),
            employee_id=m.get("employee_id", ""),
            sender=m.get("sender", "user"),
            message=m.get("message", ""),
            course_id=m.get("course_id"),
            citations=m.get("citations", []),
            tools_called=m.get("tools_called", []),
            created_at=m.get("created_at", "")
        ))
    return results

# --- 9. Dashboard (Section 5.1) ---
@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard_data(
    current_user: Optional[UserProfile] = Depends(get_current_user),
    x_employee_id: Optional[str] = Header(None)
):
    emp_id = resolve_effective_emp_id(current_user, x_employee_id=x_employee_id)
    profile = get_current_employee_profile(current_user=current_user, x_employee_id=emp_id)
    active_plan = repository.get_active_plan(emp_id)
    plan_obj = LearningPlan(**active_plan) if active_plan else None

    # Calculate metrics
    progress_records = repository.get_learning_progress(emp_id)
    total_completed_lessons = sum(1 for p in progress_records if p.get("status") == "completed")
    total_minutes = sum(p.get("time_spent_minutes", 0) for p in progress_records)
    study_hours = round(total_minutes / 60.0, 1)

    # Next recommended task
    next_task = None
    if plan_obj and plan_obj.ordered_courses:
        completed_course_ids = set(profile.completed_course_ids)
        for c in plan_obj.ordered_courses:
            if c.course_id not in completed_course_ids:
                next_task = {
                    "course_id": c.course_id,
                    "title": c.title,
                    "skill": c.skill,
                    "hours": c.hours,
                    "action": "Start Module Lessons & Complete Quiz"
                }
                break

    # Recent activities
    recent_activity = []
    for p in sorted(progress_records, key=lambda x: x.get("updated_at", ""), reverse=True)[:5]:
        recent_activity.append(DashboardActivity(
            type="lesson_progress",
            description=f"Studied lesson {p.get('lesson_id')} in {p.get('course_id')} ({p.get('status')})",
            timestamp=p.get("updated_at", "")
        ))

    assessments = repository.get_assessments(emp_id)
    for a in sorted(assessments, key=lambda x: x.get("created_at", ""), reverse=True)[:3]:
        recent_activity.append(DashboardActivity(
            type="assessment",
            description=f"Completed {a.get('assessment_id')} for {a.get('skill_id')} with score {a.get('score')}%",
            timestamp=a.get("created_at", "")
        ))

    # Overall progress percent
    overall_progress = 0.0
    if plan_obj and plan_obj.ordered_courses:
        completed_count = sum(1 for c in plan_obj.ordered_courses if c.course_id in profile.completed_course_ids)
        overall_progress = round((completed_count / len(plan_obj.ordered_courses)) * 100, 1)

    skill_summary = []
    for s in profile.skills:
        skill_summary.append({
            "skill": s.skill,
            "self": s.self_assessed_level,
            "verified": s.verified_level or 0
        })

    self_directed = get_active_plan_for_mode(emp_id, "self_directed")
    company_assigned = get_active_plan_for_mode(emp_id, "company_assigned")

    return DashboardResponse(
        employee=profile,
        active_courses_count=len(plan_obj.ordered_courses) if plan_obj else 0,
        completed_courses_count=len(profile.completed_course_ids),
        overall_progress_percent=overall_progress,
        study_hours_this_week=study_hours,
        next_recommended_task=next_task,
        recent_activity=recent_activity,
        self_directed_plan=self_directed,
        company_assigned_plan=company_assigned,
        active_plan=plan_obj,
        skill_summary=skill_summary
    )

# --- 10. Manager & Admin Endpoints (Section 5.7, Requirement 2B & 10) ---
@router.get("/manager/team", response_model=List[TeamMemberSummary])
def get_team_overview(current_user: Optional[UserProfile] = Depends(get_current_user)):
    user = current_user if isinstance(current_user, UserProfile) else None
    if user and user.role not in ["manager", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: role 'learner' is not authorized to access team management."
        )
    team_data = get_team_members_summary()
    return [TeamMemberSummary(**t) for t in team_data]

@router.post("/admin/import")
def trigger_import(current_user: Optional[UserProfile] = Depends(get_current_user)):
    user = current_user if isinstance(current_user, UserProfile) else None
    if user and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: administrator role required."
        )
    res = DataIngestionService.ingest_all()
    return res

# --- 11. Multi-LLM Provider Status (Observability & Debugging) ---
@router.get("/llm/status")
def get_llm_status():
    """
    Exposes safe provider health and configuration status for debugging.
    Zero API keys, authorization headers, or sensitive employee data are exposed.
    """
    from app.agent.providers.fallback_manager import fallback_manager
    return fallback_manager.get_provider_statuses()

