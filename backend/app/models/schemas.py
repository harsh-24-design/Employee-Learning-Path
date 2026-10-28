from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime

# --- User Roles & Authentication (Requirement 1 & 10) ---
UserRole = Literal["learner", "manager", "admin"]
CertificateType = Literal[
    "none",
    "completion_certificate",
    "assessed_certificate",
    "professional_certificate",
    "accredited_qualification"
]

class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, description="Password with minimum 6 characters")
    name: str = Field(min_length=2, description="User full name")
    role: UserRole = "learner"
    is_employee: bool = False
    employee_id: Optional[str] = None
    department: Optional[str] = "Independent Learning"

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)

class UserProfile(BaseModel):
    user_id: str
    email: str
    name: str
    role: UserRole = "learner"
    is_employee: bool = False
    employee_id: Optional[str] = None
    department: str = "Independent Learning"
    created_at: Optional[str] = None

class AuthTokenResponse(BaseModel):
    token: str
    user: UserProfile
    message: str = "Authentication successful"

class LogoutResponse(BaseModel):
    message: str = "Logged out successfully"

# --- Certificate & Multi-Platform Models (Requirement 4, 5, 6) ---
class CertificateInfo(BaseModel):
    available: bool = False
    type: CertificateType = "none"
    issuer: str = "Course Provider"
    is_included_in_price: bool = True
    separate_certificate_fee: float = 0.0
    verification_url: Optional[str] = None
    exam_requirements: Optional[str] = None

class QuizQuestion(BaseModel):
    question_id: str
    prompt: str
    options: List[str]
    correct_option_index: int

class CourseQuiz(BaseModel):
    assessment_id: str
    skill_id: str
    level: int
    max_score: int = 100
    passing_score: int = 70
    rubric: str
    questions: List[QuizQuestion]

class Lesson(BaseModel):
    lesson_id: str
    title: str
    duration_minutes: int = 45
    content: Optional[str] = ""
    module_id: Optional[str] = None
    module_title: Optional[str] = None
    explanation: Optional[str] = None
    practical_example: Optional[str] = None
    key_takeaways: Optional[List[str]] = None
    exercise: Optional[str] = None

class CourseModule(BaseModel):
    module_id: str
    title: str
    description: Optional[str] = ""
    lessons: List[Lesson] = []
    quiz: Optional[CourseQuiz] = None

class Course(BaseModel):
    course_id: str
    title: str
    provider: str = "Internal Enterprise Academy"
    platform: str = "Internal"  # "Internal", "Coursera", "edX", "Udemy", "freeCodeCamp", "LinkedIn Learning"
    description: Optional[str] = ""
    skill: str
    level: int = Field(ge=1, le=5)
    hours: float = Field(ge=0)
    cost: float = Field(ge=0)
    currency: str = "USD"
    pricing_model: str = "free"  # "free", "paid_one_time", "subscription"
    subscription_monthly_cost: Optional[float] = None
    prerequisite_id: Optional[str] = None
    is_foundation: bool = False
    source_url: Optional[str] = ""
    catalogue_status: str = "approved"
    source_verification_status: str = "verified"  # "verified", "unconfirmed"
    last_checked_date: Optional[str] = None
    certificate_info: CertificateInfo = CertificateInfo()
    lessons: List[Lesson] = []
    modules: Optional[List[CourseModule]] = []
    is_demo: bool = False
    demo_disclaimer: Optional[str] = None
    quiz: Optional[CourseQuiz] = None

# --- Skills & Competencies ---
class SkillLevelDefinition(BaseModel):
    level: int = Field(ge=0, le=5)
    description: str

class SkillInfo(BaseModel):
    skill_id: str
    name: str
    description: Optional[str] = ""
    level_definitions: Optional[Dict[int, str]] = {}

class EmployeeSkill(BaseModel):
    skill_id: str
    skill: str
    self_assessed_level: int = Field(ge=0, le=5)
    verified_level: Optional[int] = Field(None, ge=0, le=5)
    assessment_source: Optional[str] = "self"
    updated_at: Optional[str] = None

class RoleCompetency(BaseModel):
    skill: str
    required_proficiency: int = Field(ge=0, le=5)

class Role(BaseModel):
    role_name: str
    description: str
    prerequisites: Optional[List[str]] = []
    relevant_resources: Optional[List[str]] = []
    competencies: List[RoleCompetency]

class RoleCreateUpdateRequest(BaseModel):
    role_name: str
    description: str
    prerequisites: Optional[List[str]] = []
    relevant_resources: Optional[List[str]] = []
    competencies: List[RoleCompetency]

# --- Learning Preferences & Profile ---
class LearningPreferences(BaseModel):
    preferred_learning_style: str = "mixed"  # video, reading, practice, mixed
    daily_study_hours: float = 1.5
    weekly_hours_available: float = 10.0
    training_intensity: str = "normal"      # light, normal, intensive
    budget_limit: float = 500.0
    target_completion_date: Optional[str] = None
    wants_certificate: bool = False
    preferred_certificate_type: Optional[CertificateType] = None
    preferred_platforms: List[str] = []

class EmployeeProfile(BaseModel):
    employee_id: str
    employee_code: Optional[str] = None
    name: str
    department: str = "Engineering"
    target_role: Optional[str] = "Data Analyst"
    preferences: LearningPreferences = LearningPreferences()
    skills: List[EmployeeSkill] = []
    completed_course_ids: List[str] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class EmployeeProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    target_role: Optional[str] = None
    preferences: Optional[LearningPreferences] = None
    self_assessed_skills: Optional[Dict[str, int]] = None

# --- Skill Gap Analysis ---
class SkillGapItem(BaseModel):
    skill: str
    current_proficiency: int = 0
    target_proficiency: int
    gap: int
    has_catalogue_courses: bool = True
    recommended_course_ids: List[str] = []

class SkillGapAnalysisRequest(BaseModel):
    employee_id: str
    target_role: str

class SkillGapAnalysisResponse(BaseModel):
    employee_id: str
    target_role: str
    gaps: List[SkillGapItem]
    total_gaps: int
    unfulfillable_skills: List[str] = []
    role_competency_available: bool = True
    notes: Optional[str] = None

# --- Dual-Mode Learning Plans (Requirement 2 & 7) ---
PlanMode = Literal["self_directed", "company_assigned"]

class Milestone(BaseModel):
    milestone_id: str
    title: str
    description: str
    course_ids: List[str] = []
    estimated_hours: float = 0.0
    target_date: Optional[str] = None
    assessment_activity: Optional[str] = None
    is_completed: bool = False

class BudgetOptionComparison(BaseModel):
    model_type: str  # "free_audit", "paid_one_time", "monthly_subscription"
    provider_summary: str
    estimated_cost: float
    estimated_months: float = 0.0
    certificate_included: bool
    financial_assistance_available: bool = False
    financial_assistance_details: Optional[str] = None

class BudgetBreakdown(BaseModel):
    total_estimated_cost: float
    budget_limit: Optional[float] = None
    is_within_budget: bool = True
    free_alternatives_cost: float = 0.0
    paid_courses_cost: float = 0.0
    subscription_cost: float = 0.0
    certificate_fees_cost: float = 0.0
    staged_path_suggestion: Optional[str] = None
    comparisons: List[BudgetOptionComparison] = []

class LearningPlan(BaseModel):
    plan_id: str
    employee_id: str
    mode: PlanMode = "self_directed"
    target_role: str
    is_custom_goal: bool = False
    goal_description: Optional[str] = None
    current_skill_snapshot: Dict[str, int] = {}
    target_competencies: Dict[str, int] = {}
    ordered_courses: List[Course]
    total_hours: float
    total_cost: float
    estimated_weeks: float
    is_extended_timeline: bool
    budget_limit: Optional[float]
    weekly_hours: float
    training_intensity: str = "normal"
    target_completion_date: Optional[str] = None
    milestones: List[Milestone] = []
    budget_breakdown: Optional[BudgetBreakdown] = None
    remaining_gaps: List[str] = []
    deferred_courses: List[str] = []
    content_hash: str
    version: int = 1
    # Company Assigned Metadata (Requirement 2B)
    assigned_by: Optional[str] = None
    assignment_deadline: Optional[str] = None
    manager_notes: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None
    disclaimer: str = (
        "Advisory recommendation only. Completing this learning path does not guarantee "
        "certification, promotion, salary increase, or employment outcome."
    )

class PlanGenerationRequest(BaseModel):
    employee_id: str
    target_role: Optional[str] = "Data Analyst"
    mode: PlanMode = "self_directed"
    custom_skills: Optional[Dict[str, int]] = None
    goal_description: Optional[str] = None
    budget: Optional[float] = None
    weekly_hours: Optional[float] = None
    target_date: Optional[str] = None
    training_intensity: Optional[str] = "normal"
    wants_certificate: bool = False
    preferred_platform: Optional[str] = None

class CustomGoalRequest(BaseModel):
    employee_id: str
    goal_title: str
    goal_description: Optional[str] = ""
    target_skills: Dict[str, int]  # e.g., {"Python": 3, "Machine Learning": 2}
    budget: Optional[float] = 300.0
    weekly_hours: Optional[float] = 8.0

class PlanUpdateRequest(BaseModel):
    budget: Optional[float] = None
    weekly_hours: Optional[float] = None
    target_date: Optional[str] = None

# --- Manager Assignment (Requirement 2B & 10) ---
class CompanyGoalAssignmentRequest(BaseModel):
    employee_id: str
    target_role: str
    assignment_deadline: str
    budget: float = 500.0
    weekly_hours: float = 10.0
    manager_notes: Optional[str] = "Company required upskilling track"

class TeamMemberSummary(BaseModel):
    employee_id: str
    name: str
    department: str
    email: str
    has_active_assigned_plan: bool
    assigned_role: Optional[str] = None
    assigned_deadline: Optional[str] = None
    assigned_progress_percent: float = 0.0
    completed_courses_count: int = 0

# --- Progress Tracking (Requirement 8) ---
class ProgressRecordRequest(BaseModel):
    employee_id: Optional[str] = None
    course_id: str
    lesson_id: str
    status: str = "completed"  # not_started, in_progress, completed, needs_revision
    time_spent_minutes: int = 30

class LearningProgressItem(BaseModel):
    progress_id: str
    employee_id: str
    plan_id: Optional[str] = None
    course_id: str
    lesson_id: str
    status: str
    time_spent_minutes: int
    completed_at: Optional[str] = None
    updated_at: str

# --- Assessment & Quizzes (Requirement 8) ---
class QuizQuestion(BaseModel):
    question_id: str
    prompt: str
    options: List[str]
    correct_option_index: int

class CourseQuiz(BaseModel):
    assessment_id: str
    skill_id: str
    level: int
    max_score: int = 100
    passing_score: int = 70
    rubric: str
    questions: List[QuizQuestion]

class AssessmentSubmissionRequest(BaseModel):
    employee_id: Optional[str] = None
    course_id: str
    assessment_id: str
    answers: Dict[str, int]  # question_id -> selected_option_index

class AssessmentResult(BaseModel):
    assessment_id: str
    employee_id: str
    course_id: str
    skill_id: str
    score: int
    max_score: int
    passed: bool
    rubric_version: str
    evidence: str
    updated_verified_level: Optional[int] = None
    created_at: str

# --- Course-Aware Chat (Requirement 9) ---
class ChatMessage(BaseModel):
    message_id: str
    conversation_id: str
    employee_id: str
    sender: str  # user, assistant
    message: str
    course_id: Optional[str] = None
    citations: List[Dict[str, Any]] = []
    tools_called: List[Dict[str, Any]] = []
    created_at: str

class ChatConversationCreateRequest(BaseModel):
    employee_id: str
    course_id: Optional[str] = None

class ChatConversation(BaseModel):
    conversation_id: str
    employee_id: str
    course_id: Optional[str] = None
    title: str = "Learning Assistance"
    created_at: str
    updated_at: str

class ChatMessageSendRequest(BaseModel):
    employee_id: str
    message: str
    course_id: Optional[str] = None
    plan_mode: Optional[PlanMode] = "self_directed"

class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    citations: List[Dict[str, Any]] = []
    tools_called: List[Dict[str, Any]] = []
    course_id: Optional[str] = None

# --- Dashboard & Combined Views ---
class DashboardActivity(BaseModel):
    type: str  # lesson_complete, quiz_passed, plan_generated, goal_assigned
    description: str
    timestamp: str

class DashboardResponse(BaseModel):
    employee: EmployeeProfile
    active_courses_count: int
    completed_courses_count: int
    overall_progress_percent: float
    study_hours_this_week: float
    next_recommended_task: Optional[Dict[str, Any]] = None
    recent_activity: List[DashboardActivity] = []
    self_directed_plan: Optional[LearningPlan] = None
    company_assigned_plan: Optional[LearningPlan] = None
    active_plan: Optional[LearningPlan] = None
    skill_summary: List[Dict[str, Any]] = []
