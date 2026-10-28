import React, { useState, useEffect, useRef } from 'react';
import { 
  BookOpen, 
  CheckCircle, 
  Circle, 
  Clock, 
  Award, 
  Sparkles, 
  ChevronRight, 
  ChevronDown,
  CheckCircle2, 
  XCircle, 
  HelpCircle, 
  FileText, 
  Send, 
  Bot, 
  User, 
  Code2, 
  Lightbulb, 
  AlertCircle,
  RefreshCw,
  ExternalLink,
  Layers,
  ArrowRight
} from 'lucide-react';
import { Course, CourseModule, Lesson, CourseQuiz, LearningProgressItem, AssessmentResult, api } from '../lib/api';

interface CoursePageViewProps {
  empId: string;
  selectedCourseId?: string;
  onOpenChat: (courseId: string) => void;
  onRefreshStats: () => void;
}

export const CoursePageView: React.FC<CoursePageViewProps> = ({ 
  empId, 
  selectedCourseId, 
  onOpenChat,
  onRefreshStats
}) => {
  const [courses, setCourses] = useState<Course[]>([]);
  const [activeCourseId, setActiveCourseId] = useState<string>(selectedCourseId || 'C101');
  const [course, setCourse] = useState<Course | null>(null);
  const [quiz, setQuiz] = useState<CourseQuiz | null>(null);
  const [progressList, setProgressList] = useState<LearningProgressItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Expanded lesson viewer state (does NOT mark lesson as completed)
  const [expandedLessonId, setExpandedLessonId] = useState<string | null>(null);

  // Right column active sub-panel: 'tutor' or 'quiz'
  const [rightPanelTab, setRightPanelTab] = useState<'tutor' | 'quiz'>('tutor');

  // Quiz state
  const [activeQuizId, setActiveQuizId] = useState<string>('');
  const [activeQuiz, setActiveQuiz] = useState<CourseQuiz | null>(null);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [submittingQuiz, setSubmittingQuiz] = useState(false);
  const [quizResult, setQuizResult] = useState<AssessmentResult | null>(null);

  // In-Workspace AI Tutor state
  const [tutorMessages, setTutorMessages] = useState<Array<{
    sender: 'user' | 'assistant';
    text: string;
    citations?: any[];
    isError?: boolean;
  }>>([]);
  const [tutorInput, setTutorInput] = useState('');
  const [tutorSending, setTutorSending] = useState(false);
  const tutorEndRef = useRef<HTMLDivElement>(null);

  // Personal notes
  const [notes, setNotes] = useState('');

  useEffect(() => {
    loadCourses();
  }, [empId]);

  useEffect(() => {
    if (selectedCourseId) {
      setActiveCourseId(selectedCourseId);
    }
  }, [selectedCourseId]);

  useEffect(() => {
    if (activeCourseId) {
      loadCourseDetail(activeCourseId);
    }
  }, [activeCourseId, empId]);

  useEffect(() => {
    tutorEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [tutorMessages]);

  const loadCourses = async () => {
    try {
      const all = await api.getCourses();
      setCourses(all);
      if (!selectedCourseId && all.length > 0) {
        setActiveCourseId(all[0].course_id);
      }
    } catch (e) {
      console.error('Failed to load courses list:', e);
    }
  };

  const loadCourseDetail = async (cid: string) => {
    setLoading(true);
    setErrorMessage(null);
    setQuizResult(null);
    setAnswers({});
    try {
      const [cData, qData, pData] = await Promise.all([
        api.getCourse(cid),
        api.getCourseQuiz(cid).catch(() => null),
        api.getProgress(empId, cid).catch(() => [])
      ]);

      if (!cData || !cData.course_id) {
        throw new Error(`Course details for ${cid} could not be retrieved.`);
      }

      setCourse(cData);
      setQuiz(qData);
      setActiveQuiz(qData);
      setActiveQuizId(qData?.assessment_id || `QZ-${cid}`);
      setProgressList(pData || []);

      // Initialize expanded lesson to the first lesson of the first module if available
      if (cData.modules && cData.modules.length > 0 && cData.modules[0].lessons.length > 0) {
        setExpandedLessonId(cData.modules[0].lessons[0].lesson_id);
      } else if (cData.lessons && cData.lessons.length > 0) {
        setExpandedLessonId(cData.lessons[0].lesson_id);
      } else {
        setExpandedLessonId(null);
      }

      // Initialize In-Workspace AI Tutor welcome message
      setTutorMessages([
        {
          sender: 'assistant',
          text: `Welcome to the ${cData.title} workspace! I am your course-aware AI tutor grounded in these specific lessons. Ask me to explain concepts, walk through code examples, or test your understanding with practice questions.`
        }
      ]);
    } catch (e: any) {
      console.error('Failed to load course details:', e);
      setErrorMessage(e.message || `Failed to load learning content for course ${cid}. Please check backend connection.`);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectQuiz = (quizToSelect: CourseQuiz) => {
    setActiveQuiz(quizToSelect);
    setActiveQuizId(quizToSelect.assessment_id);
    setAnswers({});
    setQuizResult(null);
    setRightPanelTab('quiz');
  };

  const handleToggleLesson = async (lessonId: string, currentStatus: string, duration: number, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    const newStatus = currentStatus === 'completed' ? 'in_progress' : 'completed';
    try {
      await api.recordProgress(empId, activeCourseId, lessonId, newStatus, newStatus === 'completed' ? duration : 0);
      const updated = await api.getProgress(empId, activeCourseId);
      setProgressList(updated);
      onRefreshStats();
    } catch (e) {
      console.error('Failed to update lesson progress:', e);
    }
  };

  const handleAnswerSelect = (qid: string, optIdx: number) => {
    setAnswers(prev => ({ ...prev, [qid]: optIdx }));
  };

  const handleSubmitQuiz = async () => {
    if (!activeQuiz) return;
    setSubmittingQuiz(true);
    try {
      const res = await api.submitAssessment(empId, activeCourseId, activeQuiz.assessment_id, answers);
      setQuizResult(res);
      onRefreshStats();
    } catch (e) {
      console.error('Failed to submit quiz:', e);
    } finally {
      setSubmittingQuiz(false);
    }
  };

  const handleSendTutorQuestion = async (queryText?: string) => {
    const text = queryText || tutorInput;
    if (!text.trim() || tutorSending) return;

    setTutorMessages(prev => [...prev, { sender: 'user', text }]);
    if (!queryText) setTutorInput('');
    setTutorSending(true);

    try {
      const response = await api.sendChatMessage(empId, text, activeCourseId);
      const isErr = response.reply.startsWith('AI Service Error') || response.reply.startsWith('AI Advisor Configuration');
      setTutorMessages(prev => [
        ...prev,
        {
          sender: 'assistant',
          text: response.reply,
          citations: response.citations || [],
          isError: isErr
        }
      ]);
    } catch (e: any) {
      setTutorMessages(prev => [
        ...prev,
        {
          sender: 'assistant',
          text: `AI Tutor Connection Error: Unable to communicate with the advisory service. Please verify that backend is running.`,
          isError: true
        }
      ]);
    } finally {
      setTutorSending(false);
    }
  };

  // Quick prompt buttons adapted to current course
  const getQuickQuestions = () => {
    if (activeCourseId === 'C101') {
      return [
        'What is a Python variable?',
        'How do if/elif/else conditions work?',
        'How do I define a function in Python?'
      ];
    }
    if (activeCourseId === 'C301') {
      return [
        'What is the difference between relative and absolute references ($A$1)?',
        'How does XLOOKUP work compared to VLOOKUP?',
        'How do I use the IF and AND functions together?'
      ];
    }
    if (activeCourseId === 'C501') {
      return [
        'What is the difference between IaaS, PaaS, and SaaS?',
        'Explain the Shared Responsibility Model in cloud security',
        'What distinguishes an Availability Zone from a Cloud Region?'
      ];
    }
    return [
      `What are the core fundamentals of this course?`,
      `Show me a practical example from this course.`
    ];
  };

  if (loading && !course) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] space-y-3">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
        <p className="text-xs text-slate-500 font-medium">Loading course lessons and verified curriculum...</p>
      </div>
    );
  }

  if (errorMessage && !course) {
    return (
      <div className="p-8 bg-red-50 border border-red-200 rounded-2xl max-w-xl mx-auto text-center space-y-4 my-8">
        <AlertCircle className="w-10 h-10 text-red-600 mx-auto" />
        <h3 className="text-base font-bold text-red-900">Course Content Unavailable</h3>
        <p className="text-xs text-red-700 leading-relaxed">{errorMessage}</p>
        <div className="flex justify-center gap-3 pt-2">
          <button
            onClick={() => loadCourseDetail(activeCourseId)}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition shadow-xs"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Retry Loading Course
          </button>
          <button
            onClick={() => setActiveCourseId('C101')}
            className="px-4 py-2 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold transition"
          >
            Open Python Basics Demo
          </button>
        </div>
      </div>
    );
  }

  const completedLessonIds = new Set(
    progressList.filter(p => p.status === 'completed').map(p => p.lesson_id)
  );

  const allLessons: Lesson[] = course?.modules && course.modules.length > 0
    ? course.modules.flatMap(m => m.lessons)
    : (course?.lessons || []);

  const totalLessonsCount = allLessons.length;
  const completedLessonsCount = allLessons.filter(l => completedLessonIds.has(l.lesson_id)).length;
  const progressPercent = totalLessonsCount > 0 ? Math.round((completedLessonsCount / totalLessonsCount) * 100) : 0;

  return (
    <div className="space-y-6">
      {/* Top Header & Selector */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-bold text-emerald-800 bg-emerald-100 px-2.5 py-0.5 rounded-full flex items-center gap-1">
              <BookOpen className="w-3.5 h-3.5" /> Course Workspace
            </span>
            <span className="text-xs text-slate-500">Live RAG-Based Learning Demo</span>
          </div>
          <h2 className="text-xl font-bold text-slate-900">Interactive Learning & Doubt Resolution</h2>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs font-semibold text-slate-600">Select Course:</label>
          <select
            value={activeCourseId}
            onChange={e => setActiveCourseId(e.target.value)}
            className="text-xs px-3 py-1.5 border border-slate-300 rounded-lg bg-white font-medium focus:ring-1 focus:ring-emerald-500 outline-none shadow-2xs"
          >
            {courses.map(c => (
              <option key={c.course_id} value={c.course_id}>
                {c.course_id}: {c.title}
              </option>
            ))}
          </select>
        </div>
      </div>

      {course && (
        <div className="space-y-6">
          {/* Demo Learning Materials Notice */}
          <div className="p-3.5 bg-amber-50/90 border border-amber-200/80 rounded-xl flex items-start gap-3 text-xs text-amber-900 shadow-2xs">
            <Lightbulb className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <span className="font-bold">Demonstration Training Materials Notice:</span>
              <p className="text-[11px] text-amber-800 leading-relaxed">
                {course.demo_disclaimer || 'These modules and exercises represent prototype learning materials for skill advisory simulation and do not constitute official enterprise certification.'}
              </p>
            </div>
          </div>

          {/* Course Summary Banner */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-bold text-emerald-800 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded">
                    {course.skill} • Level {course.level}
                  </span>
                  <span className="text-xs text-slate-500 flex items-center gap-1 font-medium">
                    <Clock className="w-3.5 h-3.5" /> {course.hours} hours total
                  </span>
                  <span className="text-xs text-slate-500 font-medium">
                    {course.cost === 0 ? 'Free ($0)' : `$${course.cost}`}
                  </span>
                </div>
                <h3 className="text-xl font-bold text-slate-900">{course.title}</h3>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setRightPanelTab('tutor')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${
                    rightPanelTab === 'tutor'
                      ? 'bg-emerald-600 text-white shadow-xs'
                      : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200'
                  }`}
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  Ask AI Tutor
                </button>
                <button
                  onClick={() => setRightPanelTab('quiz')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${
                    rightPanelTab === 'quiz'
                      ? 'bg-emerald-600 text-white shadow-xs'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200 border border-slate-200'
                  }`}
                >
                  <Award className="w-3.5 h-3.5" />
                  Module Quizzes
                </button>
              </div>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              {course.description || 'Master foundational workflows, syntax, and applied problem solving with structured modules.'}
            </p>

            {/* Overall Course Progress Bar */}
            <div className="space-y-1.5 pt-2 border-t border-slate-100">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-slate-700">Course Progress</span>
                <span className="text-slate-500 font-medium">
                  {completedLessonsCount} of {totalLessonsCount} lessons completed ({progressPercent}%)
                </span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                <div 
                  className="bg-emerald-500 h-2 rounded-full transition-all duration-300" 
                  style={{ width: `${progressPercent}%` }} 
                />
              </div>
            </div>
          </div>

          {/* Main Grid: Left Column = Modules & Lessons; Right Column = AI Tutor / Quizzes */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            
            {/* Left 7 spans: Structured Modules & Interactive Lessons */}
            <div className="lg:col-span-7 space-y-5">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <Layers className="w-4 h-4 text-emerald-600" />
                  Course Modules & Substantive Lessons
                </h4>
                <span className="text-xs text-slate-400 italic">
                  *Click a lesson to study explanation, code, and exercises.
                </span>
              </div>

              {course.modules && course.modules.length > 0 ? (
                // Multi-Module Render
                <div className="space-y-4">
                  {course.modules.map((mod, modIdx) => (
                    <div 
                      key={mod.module_id}
                      className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden"
                    >
                      <div className="p-4 bg-slate-50/70 border-b border-slate-200/80 flex flex-col sm:flex-row justify-between sm:items-center gap-2">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] font-bold text-slate-600 bg-slate-200/80 px-2 py-0.5 rounded uppercase tracking-wider">
                              Module {modIdx + 1}
                            </span>
                            <h5 className="font-bold text-xs text-slate-900">{mod.title}</h5>
                          </div>
                          {mod.description && (
                            <p className="text-[11px] text-slate-500 mt-1">{mod.description}</p>
                          )}
                        </div>

                        {mod.quiz && (
                          <button
                            onClick={() => handleSelectQuiz(mod.quiz!)}
                            className="px-2.5 py-1 bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 rounded text-[11px] font-semibold flex items-center gap-1 transition self-start sm:self-auto shrink-0 shadow-2xs"
                          >
                            <Award className="w-3 h-3 text-emerald-600" />
                            Module Quiz
                          </button>
                        )}
                      </div>

                      <div className="p-3 space-y-2.5">
                        {mod.lessons.map((lesson) => {
                          const isCompleted = completedLessonIds.has(lesson.lesson_id);
                          const isExpanded = expandedLessonId === lesson.lesson_id;

                          return (
                            <div 
                              key={lesson.lesson_id}
                              className={`rounded-xl border transition overflow-hidden ${
                                isCompleted 
                                  ? 'bg-emerald-50/30 border-emerald-200' 
                                  : 'bg-white border-slate-200 hover:border-slate-300'
                              }`}
                            >
                              {/* Lesson Header Row */}
                              <div 
                                onClick={() => setExpandedLessonId(isExpanded ? null : lesson.lesson_id)}
                                className="p-3 flex items-center justify-between gap-3 cursor-pointer select-none"
                              >
                                <div className="flex items-center gap-3">
                                  {/* Mark Complete Checkbox Button (Only clicking this marks completed) */}
                                  <button
                                    type="button"
                                    onClick={(e) => handleToggleLesson(lesson.lesson_id, isCompleted ? 'completed' : 'not_started', lesson.duration_minutes, e)}
                                    className="text-slate-400 hover:text-emerald-600 transition shrink-0"
                                    title={isCompleted ? 'Mark as Incomplete' : 'Mark as Completed'}
                                  >
                                    {isCompleted ? (
                                      <CheckCircle className="w-5 h-5 text-emerald-600" />
                                    ) : (
                                      <Circle className="w-5 h-5 text-slate-400 hover:text-slate-600" />
                                    )}
                                  </button>

                                  <div>
                                    <div className={`text-xs font-bold flex items-center gap-2 ${
                                      isCompleted ? 'text-slate-600' : 'text-slate-900'
                                    }`}>
                                      {lesson.title}
                                    </div>
                                    <span className="text-[10px] text-slate-400 font-medium">
                                      {lesson.duration_minutes} min study session
                                    </span>
                                  </div>
                                </div>

                                <div className="flex items-center gap-2 shrink-0">
                                  <span className={`text-[10px] px-2 py-0.5 rounded font-semibold ${
                                    isCompleted 
                                      ? 'bg-emerald-100 text-emerald-800' 
                                      : 'bg-slate-100 text-slate-600'
                                  }`}>
                                    {isCompleted ? 'Completed' : 'To Learn'}
                                  </span>
                                  {isExpanded ? (
                                    <ChevronDown className="w-4 h-4 text-slate-400" />
                                  ) : (
                                    <ChevronRight className="w-4 h-4 text-slate-400" />
                                  )}
                                </div>
                              </div>

                              {/* Substantive Expanded Lesson Content */}
                              {isExpanded && (
                                <div className="px-4 pb-4 pt-1 border-t border-slate-100 space-y-3.5 bg-slate-50/40 text-xs">
                                  {/* 1. Concept Explanation */}
                                  <div className="space-y-1">
                                    <span className="font-bold text-slate-800 flex items-center gap-1.5 text-xs">
                                      <BookOpen className="w-3.5 h-3.5 text-emerald-600" />
                                      Concept Explanation
                                    </span>
                                    <p className="text-slate-700 leading-relaxed text-[11.5px] bg-white p-3 rounded-lg border border-slate-200/80">
                                      {lesson.explanation || lesson.content || 'Foundational explanation and syntax breakdown.'}
                                    </p>
                                  </div>

                                  {/* 2. Practical Example & Code / Scenario */}
                                  {lesson.practical_example && (
                                    <div className="space-y-1">
                                      <span className="font-bold text-slate-800 flex items-center gap-1.5 text-xs">
                                        <Code2 className="w-3.5 h-3.5 text-blue-600" />
                                        Practical Example & Expected Output
                                      </span>
                                      <div className="bg-slate-900 text-slate-100 p-3 rounded-lg font-mono text-[11px] overflow-x-auto leading-relaxed border border-slate-800">
                                        <pre className="whitespace-pre-wrap">{lesson.practical_example}</pre>
                                      </div>
                                    </div>
                                  )}

                                  {/* 3. Key Takeaways */}
                                  {lesson.key_takeaways && lesson.key_takeaways.length > 0 && (
                                    <div className="space-y-1">
                                      <span className="font-bold text-slate-800 flex items-center gap-1.5 text-xs">
                                        <Lightbulb className="w-3.5 h-3.5 text-amber-500" />
                                        Key Takeaways
                                      </span>
                                      <ul className="bg-white p-3 rounded-lg border border-slate-200/80 space-y-1 text-[11px] text-slate-700 list-disc pl-5">
                                        {lesson.key_takeaways.map((point, pIdx) => (
                                          <li key={pIdx}>{point}</li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}

                                  {/* 4. Hands-on Exercise */}
                                  {lesson.exercise && (
                                    <div className="space-y-1.5">
                                      <span className="font-bold text-slate-800 flex items-center gap-1.5 text-xs">
                                        <HelpCircle className="w-3.5 h-3.5 text-purple-600" />
                                        Hands-on Exercise
                                      </span>
                                      <div className="p-3 bg-purple-50/60 border border-purple-200 rounded-lg text-[11px] text-purple-950 flex flex-col sm:flex-row justify-between sm:items-center gap-2">
                                        <p className="leading-relaxed font-medium">{lesson.exercise}</p>
                                        <button
                                          onClick={() => {
                                            setRightPanelTab('tutor');
                                            handleSendTutorQuestion(`In lesson '${lesson.title}', how do I solve the exercise: ${lesson.exercise}`);
                                          }}
                                          className="px-2.5 py-1 bg-purple-600 hover:bg-purple-700 text-white rounded text-[10px] font-bold shrink-0 self-start sm:self-auto transition shadow-2xs"
                                        >
                                          Ask Tutor for Hint
                                        </button>
                                      </div>
                                    </div>
                                  )}

                                  {/* Lesson Completion Action Button */}
                                  <div className="pt-2 flex justify-between items-center border-t border-slate-200/60">
                                    <span className="text-[11px] text-slate-400">
                                      {isCompleted ? 'Marked complete for your user ID.' : 'Ready to mark complete after studying.'}
                                    </span>
                                    <button
                                      onClick={() => handleToggleLesson(lesson.lesson_id, isCompleted ? 'completed' : 'not_started', lesson.duration_minutes)}
                                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
                                        isCompleted
                                          ? 'bg-slate-200 hover:bg-slate-300 text-slate-700'
                                          : 'bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs'
                                      }`}
                                    >
                                      {isCompleted ? (
                                        <>
                                          <CheckCircle2 className="w-3.5 h-3.5" />
                                          Mark Incomplete
                                        </>
                                      ) : (
                                        <>
                                          <CheckCircle className="w-3.5 h-3.5" />
                                          Mark Lesson Complete
                                        </>
                                      )}
                                    </button>
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                // Flat Lessons Fallback
                <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
                  {course.lessons.map(lesson => (
                    <div key={lesson.lesson_id} className="p-3 bg-slate-50 rounded-lg flex items-center justify-between">
                      <span className="font-bold text-xs">{lesson.title}</span>
                      <span className="text-xs text-slate-500">{lesson.duration_minutes} min</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Personal Notes Box */}
              <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs space-y-2">
                <h4 className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-slate-500" />
                  Course Study Notes (Auto-saved)
                </h4>
                <textarea
                  value={notes}
                  onChange={e => setNotes(e.target.value)}
                  placeholder="Record your personal notes, code snippets, or takeaways for this course..."
                  rows={3}
                  className="w-full text-xs p-3 border border-slate-300 rounded-xl outline-none focus:ring-1 focus:ring-emerald-500"
                />
              </div>
            </div>

            {/* Right 5 spans: In-Workspace AI Tutor OR Module Quiz Assessment */}
            <div className="lg:col-span-5 space-y-4">
              {/* Tab Selector Header */}
              <div className="bg-white p-1 rounded-xl border border-slate-200 flex text-xs font-bold shadow-2xs">
                <button
                  onClick={() => setRightPanelTab('tutor')}
                  className={`flex-1 py-1.5 rounded-lg flex items-center justify-center gap-1.5 transition ${
                    rightPanelTab === 'tutor'
                      ? 'bg-emerald-600 text-white shadow-2xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  Ask AI Tutor (RAG)
                </button>
                <button
                  onClick={() => setRightPanelTab('quiz')}
                  className={`flex-1 py-1.5 rounded-lg flex items-center justify-center gap-1.5 transition ${
                    rightPanelTab === 'quiz'
                      ? 'bg-emerald-600 text-white shadow-2xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <Award className="w-3.5 h-3.5" />
                  Quizzes & Verification
                </button>
              </div>

              {/* View 1: In-Workspace AI Tutor */}
              {rightPanelTab === 'tutor' && (
                <div className="bg-white rounded-2xl border border-slate-200/90 shadow-xs flex flex-col h-[650px] overflow-hidden">
                  {/* Tutor Panel Header */}
                  <div className="p-3.5 bg-slate-50/80 border-b border-slate-200 flex justify-between items-center">
                    <div>
                      <div className="flex items-center gap-1.5">
                        <Bot className="w-4 h-4 text-emerald-600" />
                        <h4 className="font-bold text-xs text-slate-900">Course AI Tutor</h4>
                      </div>
                      <p className="text-[10px] text-slate-500 mt-0.5">
                        Grounded in <span className="font-semibold text-slate-700">{course.title}</span> material
                      </p>
                    </div>
                    <span className="text-[10px] bg-emerald-100 text-emerald-800 font-bold px-2 py-0.5 rounded">
                      Chroma RAG
                    </span>
                  </div>

                  {/* Quick Prompts */}
                  <div className="p-2.5 bg-slate-50/40 border-b border-slate-100 flex flex-wrap gap-1.5">
                    {getQuickQuestions().map((q, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleSendTutorQuestion(q)}
                        disabled={tutorSending}
                        className="text-[10.5px] px-2.5 py-1 bg-white hover:bg-emerald-50 hover:border-emerald-300 text-slate-700 hover:text-emerald-900 border border-slate-200 rounded-full transition shadow-2xs text-left"
                      >
                        {q}
                      </button>
                    ))}
                  </div>

                  {/* Messages Feed */}
                  <div className="flex-1 p-3.5 overflow-y-auto space-y-3">
                    {tutorMessages.map((msg, idx) => (
                      <div 
                        key={idx}
                        className={`flex gap-2.5 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
                      >
                        {msg.sender === 'assistant' && (
                          <div className="w-6 h-6 rounded-full bg-emerald-100 flex items-center justify-center shrink-0 mt-0.5">
                            <Bot className="w-3.5 h-3.5 text-emerald-700" />
                          </div>
                        )}

                        <div className={`max-w-[85%] rounded-2xl p-3 text-xs leading-relaxed ${
                          msg.sender === 'user'
                            ? 'bg-emerald-600 text-white rounded-tr-none'
                            : msg.isError
                              ? 'bg-red-50 text-red-900 border border-red-200 rounded-tl-none'
                              : 'bg-slate-100/90 text-slate-900 border border-slate-200/70 rounded-tl-none'
                        }`}>
                          <div className="whitespace-pre-wrap">{msg.text}</div>

                          {/* Source Citations Tag */}
                          {msg.citations && msg.citations.length > 0 && (
                            <div className="mt-2.5 pt-2 border-t border-slate-200/80 space-y-1">
                              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                                Verified Lesson Citations:
                              </span>
                              {msg.citations.map((c, cIdx) => (
                                <div key={cIdx} className="text-[10.5px] bg-white/80 p-1.5 rounded border border-slate-200 text-slate-700 flex items-center gap-1">
                                  <BookOpen className="w-3 h-3 text-emerald-600 shrink-0" />
                                  <span className="font-semibold">{c.source_reference || `${c.course_title} - ${c.lesson_title}`}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        {msg.sender === 'user' && (
                          <div className="w-6 h-6 rounded-full bg-slate-200 flex items-center justify-center shrink-0 mt-0.5">
                            <User className="w-3.5 h-3.5 text-slate-600" />
                          </div>
                        )}
                      </div>
                    ))}

                    {tutorSending && (
                      <div className="flex gap-2.5 items-center text-xs text-slate-500">
                        <div className="w-6 h-6 rounded-full bg-emerald-100 flex items-center justify-center shrink-0">
                          <Bot className="w-3.5 h-3.5 text-emerald-700" />
                        </div>
                        <div className="flex items-center gap-1.5 bg-slate-100 p-2.5 rounded-xl border border-slate-200">
                          <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-emerald-600"></div>
                          <span className="text-[11px] font-medium">Retrieving lesson chunks & generating answer...</span>
                        </div>
                      </div>
                    )}
                    <div ref={tutorEndRef} />
                  </div>

                  {/* Input Box */}
                  <div className="p-3 bg-white border-t border-slate-200 flex items-center gap-2">
                    <input
                      type="text"
                      value={tutorInput}
                      onChange={e => setTutorInput(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && handleSendTutorQuestion()}
                      placeholder={`Ask tutor about ${course.title}...`}
                      disabled={tutorSending}
                      className="flex-1 text-xs px-3 py-2 border border-slate-300 rounded-xl outline-none focus:ring-1 focus:ring-emerald-500"
                    />
                    <button
                      onClick={() => handleSendTutorQuestion()}
                      disabled={tutorSending || !tutorInput.trim()}
                      className="p-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white rounded-xl transition shadow-xs"
                    >
                      <Send className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              )}

              {/* View 2: Module Quiz Assessment */}
              {rightPanelTab === 'quiz' && (
                <div className="bg-white p-5 rounded-2xl border border-slate-200/90 shadow-xs space-y-4">
                  <div className="flex justify-between items-start">
                    <div>
                      <h4 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                        <Award className="w-4 h-4 text-emerald-600" />
                        Practical Quiz & Rubric Verification
                      </h4>
                      <p className="text-xs text-slate-500 mt-0.5">
                        Evaluating verified skill proficiency for {course.skill} (Level {course.level})
                      </p>
                    </div>
                  </div>

                  {/* Quiz Selector */}
                  {course.modules && course.modules.length > 0 && (
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-slate-700">Select Quiz Assessment:</label>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-1.5">
                        {course.modules.map((m, idx) => (
                          <button
                            key={m.module_id}
                            onClick={() => m.quiz && handleSelectQuiz(m.quiz)}
                            className={`p-2 rounded-lg text-left text-[11px] font-bold border transition ${
                              activeQuizId === m.quiz?.assessment_id
                                ? 'bg-emerald-50 border-emerald-300 text-emerald-900'
                                : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100'
                            }`}
                          >
                            Module {idx + 1} Quiz
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {activeQuiz ? (
                    <div className="space-y-4 pt-1">
                      <div className="text-xs bg-slate-50 p-3 rounded-xl border border-slate-200 text-slate-700 space-y-1">
                        <div className="font-bold flex items-center gap-1">
                          <span>Passing Criteria:</span>
                          <span className="text-emerald-700">&ge; {activeQuiz.passing_score}%</span>
                        </div>
                        <p className="text-[11px] text-slate-500 leading-relaxed">{activeQuiz.rubric}</p>
                      </div>

                      {/* Question List */}
                      <div className="space-y-4 max-h-[420px] overflow-y-auto pr-1">
                        {activeQuiz.questions.map((q, qIndex) => (
                          <div key={q.question_id} className="space-y-2 border-b border-slate-100 pb-3 last:border-0 last:pb-0">
                            <p className="text-xs font-bold text-slate-800">
                              {qIndex + 1}. {q.prompt}
                            </p>
                            <div className="space-y-1.5 pl-1">
                              {q.options.map((opt, optIdx) => (
                                <label 
                                  key={optIdx} 
                                  className={`flex items-center gap-2 text-xs p-2 rounded-lg cursor-pointer transition ${
                                    answers[q.question_id] === optIdx 
                                      ? 'bg-emerald-50 text-emerald-900 border border-emerald-300 font-medium' 
                                      : 'hover:bg-slate-50 text-slate-600 border border-transparent'
                                  }`}
                                >
                                  <input
                                    type="radio"
                                    name={`q_${activeQuiz.assessment_id}_${q.question_id}`}
                                    checked={answers[q.question_id] === optIdx}
                                    onChange={() => handleAnswerSelect(q.question_id, optIdx)}
                                    className="accent-emerald-600"
                                  />
                                  <span>{opt}</span>
                                </label>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>

                      <button
                        onClick={handleSubmitQuiz}
                        disabled={submittingQuiz || Object.keys(answers).length < activeQuiz.questions.length}
                        className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white rounded-xl text-xs font-bold transition shadow-xs"
                      >
                        {submittingQuiz ? 'Evaluating Answers...' : 'Submit Assessment for Rubric Grading'}
                      </button>

                      {/* Quiz Result Output */}
                      {quizResult && (
                        <div className={`p-4 rounded-xl border mt-3 space-y-2 ${
                          quizResult.passed ? 'bg-emerald-50 border-emerald-300 text-emerald-900' : 'bg-red-50 border-red-300 text-red-900'
                        }`}>
                          <div className="flex items-center gap-2 font-bold text-xs">
                            {quizResult.passed ? (
                              <>
                                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                                Assessment Passed (Score: {quizResult.score}%)
                              </>
                            ) : (
                              <>
                                <XCircle className="w-4 h-4 text-red-600" />
                                Assessment Failed (Score: {quizResult.score}%)
                              </>
                            )}
                          </div>
                          <p className="text-[11px] leading-relaxed">{quizResult.evidence}</p>
                          {quizResult.passed && quizResult.updated_verified_level && (
                            <div className="text-[11px] font-bold bg-white/80 p-2.5 rounded-lg border border-emerald-200">
                              Verified proficiency in {quizResult.skill_id} elevated to Level {quizResult.updated_verified_level}/5!
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ) : (
                    <p className="text-xs text-slate-500">No quiz available for this selection.</p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
