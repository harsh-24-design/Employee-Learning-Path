import React, { useState, useEffect } from 'react';
import { 
  GitFork, 
  Clock, 
  DollarSign, 
  AlertTriangle, 
  CheckCircle2, 
  ArrowRight, 
  RefreshCw, 
  Sliders, 
  HelpCircle,
  ShieldAlert,
  Award,
  Layers,
  Calendar,
  Sparkles,
  ExternalLink,
  Info,
  Check
} from 'lucide-react';
import { LearningPlan, PlanMode, Course, api } from '../lib/api';

interface RoadmapViewProps {
  empId: string;
  onNavigateToCourse: (courseId: string) => void;
}

export const RoadmapView: React.FC<RoadmapViewProps> = ({ empId, onNavigateToCourse }) => {
  const [activeMode, setActiveMode] = useState<PlanMode>('self_directed');
  const [selfPlan, setSelfPlan] = useState<LearningPlan | null>(null);
  const [companyPlan, setCompanyPlan] = useState<LearningPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);

  // Dynamic quick sliders
  const [hoursSlider, setHoursSlider] = useState(10);
  const [budgetSlider, setBudgetSlider] = useState(500);

  // Quick Onboarding / Generator state for new users
  const [roles, setRoles] = useState<string[]>(['Data Analyst', 'Data Engineer', 'Business Analyst', 'Python Developer']);
  const [selectedRole, setSelectedRole] = useState('Data Analyst');
  const [isCustom, setIsCustom] = useState(false);
  const [customGoal, setCustomGoal] = useState('');
  const [onboardHours, setOnboardHours] = useState(10);
  const [onboardBudget, setOnboardBudget] = useState(500);
  const [onboardIntensity, setOnboardIntensity] = useState('normal');
  const [onboardCert, setOnboardCert] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    loadPlans();
    loadRoles();
  }, [empId]);

  const loadRoles = async () => {
    try {
      const r = await api.getRoles();
      if (r && r.length > 0) {
        setRoles(r.map(item => item.role_name));
      }
    } catch (e) {
      console.warn('Could not load roles:', e);
    }
  };

  const handleGenerateOnboarding = async (e: React.FormEvent) => {
    e.preventDefault();
    setGenerating(true);
    try {
      const roleToUse = isCustom ? customGoal.trim() : selectedRole;
      if (!roleToUse) return;
      const plan = await api.generateRoadmap(
        empId,
        roleToUse,
        onboardBudget,
        onboardHours,
        'self_directed',
        onboardIntensity,
        onboardCert
      );
      setSelfPlan(plan);
    } catch (err) {
      console.error('Failed to generate roadmap:', err);
    } finally {
      setGenerating(false);
    }
  };

  const loadPlans = async () => {
    setLoading(true);
    try {
      const [sPlan, cPlan] = await Promise.all([
        api.getSelfDirectedPlan(empId),
        api.getCompanyAssignedPlan(empId)
      ]);
      setSelfPlan(sPlan);
      setCompanyPlan(cPlan);

      const current = activeMode === 'company_assigned' && cPlan ? cPlan : sPlan;
      if (current) {
        setHoursSlider(current.weekly_hours);
        setBudgetSlider(current.budget_limit || 500);
      }
    } catch (e) {
      console.error('Failed to load roadmap plans:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateConstraints = async () => {
    setUpdating(true);
    try {
      const updated = await api.updateCurrentPlan(empId, budgetSlider, hoursSlider);
      if (activeMode === 'self_directed') {
        setSelfPlan(updated);
      } else {
        setCompanyPlan(updated);
      }
    } catch (e) {
      console.error('Failed to update plan constraints:', e);
    } finally {
      setUpdating(false);
    }
  };

  const currentPlan = activeMode === 'company_assigned' ? companyPlan : selfPlan;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Dual-Mode Selector Tabs (Requirement 2 & 7) */}
      <div className="bg-white p-2 rounded-2xl border border-slate-200 shadow-xs flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <div className="flex bg-slate-100 p-1 rounded-xl text-xs w-full sm:w-auto">
          <button
            onClick={() => setActiveMode('self_directed')}
            className={`flex-1 sm:flex-none px-4 py-2 rounded-lg font-bold transition flex items-center justify-center gap-2 ${
              activeMode === 'self_directed'
                ? 'bg-white text-emerald-800 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <span>🎯 Personal Self-Directed Plan</span>
            {selfPlan && (
              <span className="text-[10px] bg-emerald-100 text-emerald-800 px-1.5 py-0.2 rounded-full">
                v{selfPlan.version}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveMode('company_assigned')}
            className={`flex-1 sm:flex-none px-4 py-2 rounded-lg font-bold transition flex items-center justify-center gap-2 ${
              activeMode === 'company_assigned'
                ? 'bg-white text-blue-800 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <span>🏢 Company-Assigned Plan</span>
            {companyPlan ? (
              <span className="text-[10px] bg-blue-100 text-blue-800 px-1.5 py-0.2 rounded-full">
                Active
              </span>
            ) : (
              <span className="text-[10px] text-slate-400">None</span>
            )}
          </button>
        </div>

        {activeMode === 'company_assigned' && companyPlan && (
          <div className="text-xs text-blue-900 bg-blue-50 border border-blue-200 px-3 py-1.5 rounded-lg flex items-center gap-2">
            <span className="font-semibold">Assigned by:</span> {companyPlan.assigned_by || 'Manager'} • 
            <span className="font-semibold">Deadline:</span> {companyPlan.assignment_deadline || 'Open'}
          </div>
        )}
      </div>

      {!currentPlan ? (
        activeMode === 'company_assigned' ? (
          <div className="text-center py-12 bg-white rounded-2xl border border-slate-200 shadow-xs">
            <GitFork className="w-12 h-12 text-slate-400 mx-auto mb-3" />
            <h3 className="text-base font-bold text-slate-800">
              No company-assigned learning goal has been assigned yet.
            </h3>
            <p className="text-xs text-slate-500 mt-1 mb-4 max-w-md mx-auto">
              Company-assigned learning is assigned by managers to support organizational goals. You are free to pursue personal goals independently at any time.
            </p>
            <button
              onClick={() => setActiveMode('self_directed')}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold transition shadow-xs"
            >
              Switch to Personal Self-Directed Plan
            </button>
          </div>
        ) : (
          <div className="bg-white rounded-2xl border border-slate-200 p-6 sm:p-8 shadow-xs">
            <div className="max-w-2xl mx-auto">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-800 flex items-center justify-center shrink-0">
                  <Sparkles className="w-5 h-5 text-emerald-600" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-900">
                    Create Your Personalized Learning Roadmap
                  </h3>
                  <p className="text-xs text-slate-500">
                    Select a target role or enter any career ambition. Our AI will build an optimized milestone path within your budget and time schedule.
                  </p>
                </div>
              </div>

              <form onSubmit={handleGenerateOnboarding} className="mt-6 space-y-5">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-2">
                    What career role or skill track do you want to learn?
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-3">
                    {roles.map(r => (
                      <button
                        key={r}
                        type="button"
                        onClick={() => {
                          setSelectedRole(r);
                          setIsCustom(false);
                        }}
                        className={`p-3 rounded-xl border text-left text-xs font-medium transition flex items-center justify-between ${
                          !isCustom && selectedRole === r
                            ? 'border-emerald-600 bg-emerald-50/60 text-emerald-900 font-bold ring-1 ring-emerald-600'
                            : 'border-slate-200 hover:border-slate-300 text-slate-700 bg-slate-50/50'
                        }`}
                      >
                        <span>{r}</span>
                        {!isCustom && selectedRole === r && (
                          <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                        )}
                      </button>
                    ))}
                  </div>

                  <button
                    type="button"
                    onClick={() => setIsCustom(!isCustom)}
                    className={`text-xs font-semibold px-3 py-1.5 rounded-lg border transition ${
                      isCustom 
                        ? 'border-emerald-600 bg-emerald-50 text-emerald-800' 
                        : 'border-slate-300 text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    {isCustom ? '✓ Custom Goal Selected' : '+ Enter Custom Goal / Skill Focus'}
                  </button>

                  {isCustom && (
                    <div className="mt-3">
                      <input
                        type="text"
                        required
                        value={customGoal}
                        onChange={e => setCustomGoal(e.target.value)}
                        placeholder="e.g. Python for Data Science, Cloud Architect, Generative AI"
                        className="w-full text-xs p-3 bg-slate-50 border border-emerald-500 rounded-xl outline-none focus:ring-2 focus:ring-emerald-500"
                      />
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-100">
                  <div>
                    <div className="flex justify-between items-center mb-1">
                      <label className="text-xs font-semibold text-slate-700">Weekly Study Time</label>
                      <span className="text-xs font-bold text-emerald-700">{onboardHours} hrs/week</span>
                    </div>
                    <input
                      type="range"
                      min="3"
                      max="40"
                      step="1"
                      value={onboardHours}
                      onChange={e => setOnboardHours(Number(e.target.value))}
                      className="w-full accent-emerald-600 cursor-pointer"
                    />
                    <div className="flex justify-between text-[10px] text-slate-400 mt-0.5">
                      <span>3 hrs (Light)</span>
                      <span>15 hrs (Standard)</span>
                      <span>40 hrs (Full-time)</span>
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between items-center mb-1">
                      <label className="text-xs font-semibold text-slate-700">Budget Limit</label>
                      <span className="text-xs font-bold text-emerald-700">${onboardBudget}</span>
                    </div>
                    <input
                      type="range"
                      min="50"
                      max="1500"
                      step="50"
                      value={onboardBudget}
                      onChange={e => setOnboardBudget(Number(e.target.value))}
                      className="w-full accent-emerald-600 cursor-pointer"
                    />
                    <div className="flex justify-between text-[10px] text-slate-400 mt-0.5">
                      <span>$50</span>
                      <span>$500</span>
                      <span>$1,500</span>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Training Pace</label>
                    <select
                      value={onboardIntensity}
                      onChange={e => setOnboardIntensity(e.target.value)}
                      className="w-full text-xs p-2.5 bg-slate-50 border border-slate-300 rounded-xl outline-none focus:ring-2 focus:ring-emerald-500"
                    >
                      <option value="light">Light (Steady, 1-2 modules/week)</option>
                      <option value="normal">Normal (Standard recommended pacing)</option>
                      <option value="intensive">Intensive (Accelerated bootcamp mode)</option>
                    </select>
                  </div>

                  <div className="flex items-center sm:pt-6">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={onboardCert}
                        onChange={e => setOnboardCert(e.target.checked)}
                        className="rounded text-emerald-600 focus:ring-emerald-500 w-4 h-4"
                      />
                      <span className="text-xs text-slate-700 font-medium">
                        Target courses offering certificates
                      </span>
                    </label>
                  </div>
                </div>

                <div className="pt-4 border-t border-slate-100 flex justify-end">
                  <button
                    type="submit"
                    disabled={generating}
                    className="w-full sm:w-auto px-6 py-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition shadow-sm flex items-center justify-center gap-2 disabled:opacity-60"
                  >
                    {generating ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        Generating Roadmap with Gemini AI...
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-4 h-4" />
                        Generate & Save My Personalized Roadmap
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )
      ) : (
        <>
          {/* Header Summary */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 pb-4 border-b border-slate-100">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full ${
                    currentPlan.mode === 'company_assigned' 
                      ? 'bg-blue-100 text-blue-800' 
                      : 'bg-emerald-100 text-emerald-800'
                  }`}>
                    {currentPlan.mode === 'company_assigned' ? 'Company Requirement' : 'Self-Directed Career Goal'}
                  </span>
                  <span className="text-xs text-slate-400">Plan Version {currentPlan.version}</span>
                  {currentPlan.training_intensity && (
                    <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-md capitalize">
                      {currentPlan.training_intensity} Pace
                    </span>
                  )}
                </div>
                <h2 className="text-2xl font-bold text-slate-900">{currentPlan.target_role}</h2>
                {currentPlan.goal_description && (
                  <p className="text-xs text-slate-600 mt-1 italic">"{currentPlan.goal_description}"</p>
                )}
                {currentPlan.manager_notes && (
                  <p className="text-xs text-blue-700 mt-1 bg-blue-50/70 p-2 rounded-lg border border-blue-100">
                    <strong>Manager Note:</strong> {currentPlan.manager_notes}
                  </p>
                )}
              </div>

              {/* Stats Highlights */}
              <div className="flex gap-4 shrink-0 text-right">
                <div>
                  <span className="text-[11px] text-slate-400 uppercase tracking-wider block">Estimated Duration</span>
                  <span className="text-lg font-bold text-slate-800">{currentPlan.estimated_weeks} weeks</span>
                  <span className="text-[11px] text-slate-500 block">({currentPlan.total_hours} hrs total)</span>
                </div>
                <div>
                  <span className="text-[11px] text-slate-400 uppercase tracking-wider block">Estimated Cost</span>
                  <span className="text-lg font-bold text-emerald-700">${currentPlan.total_cost.toFixed(2)}</span>
                  <span className="text-[11px] text-slate-500 block">Budget: ${currentPlan.budget_limit || 'None'}</span>
                </div>
              </div>
            </div>

            {/* Quick Adjustment Sliders */}
            <div className="mt-4 pt-3 flex flex-col md:flex-row items-center gap-4">
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-700 shrink-0">
                <Sliders className="w-4 h-4 text-emerald-600" />
                <span>Adjust Constraints:</span>
              </div>

              <div className="flex-1 grid grid-cols-1 sm:grid-cols-2 gap-4 w-full">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500 whitespace-nowrap">Weekly Study:</span>
                  <input
                    type="range"
                    min="1"
                    max="25"
                    step="0.5"
                    value={hoursSlider}
                    onChange={e => setHoursSlider(Number(e.target.value))}
                    className="flex-1 accent-emerald-600"
                  />
                  <span className="text-xs font-bold w-12 text-right">{hoursSlider}h/wk</span>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500 whitespace-nowrap">Budget Cap:</span>
                  <input
                    type="range"
                    min="0"
                    max="1000"
                    step="25"
                    value={budgetSlider}
                    onChange={e => setBudgetSlider(Number(e.target.value))}
                    className="flex-1 accent-emerald-600"
                  />
                  <span className="text-xs font-bold w-12 text-right">${budgetSlider}</span>
                </div>
              </div>

              <button
                onClick={handleUpdateConstraints}
                disabled={updating}
                className="px-4 py-1.5 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition shrink-0"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${updating ? 'animate-spin' : ''}`} />
                {updating ? 'Recalculating...' : 'Update Plan'}
              </button>
            </div>
          </div>

          {/* Extended Timeline Alert if applicable */}
          {currentPlan.is_extended_timeline && (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <strong>Extended Timeline Plan Active:</strong> Weekly study availability is {currentPlan.weekly_hours} hrs/week (≤ 3.0 hrs). Completion is projected across {currentPlan.estimated_weeks} weeks.
              </div>
            </div>
          )}

          {/* Personalized Milestones Timeline (Requirement 7) */}
          {currentPlan.milestones && currentPlan.milestones.length > 0 && (
            <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <Layers className="w-5 h-5 text-emerald-600" />
                Structured Learning Milestones & Schedule
              </h3>
              <p className="text-xs text-slate-500">
                Paced milestones scheduled according to your weekly availability and training intensity.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
                {currentPlan.milestones.map((m, idx) => (
                  <div key={m.milestone_id} className="p-4 bg-slate-50 rounded-xl border border-slate-200 flex flex-col justify-between">
                    <div>
                      <div className="flex justify-between items-start mb-2">
                        <span className="text-xs font-bold text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded-full">
                          {m.milestone_id}
                        </span>
                        {m.target_date && (
                          <span className="text-[11px] text-slate-500 flex items-center gap-1">
                            <Calendar className="w-3 h-3 text-slate-400" /> {m.target_date}
                          </span>
                        )}
                      </div>
                      <h4 className="font-bold text-sm text-slate-900 mb-1">{m.title}</h4>
                      <p className="text-xs text-slate-600 mb-3">{m.description}</p>
                    </div>

                    <div className="pt-3 border-t border-slate-200/60 text-xs">
                      <span className="text-slate-400 text-[10px] uppercase tracking-wider block mb-1">
                        Assessment Activity
                      </span>
                      <span className="text-slate-700 font-medium">{m.assessment_activity}</span>
                      <span className="text-[11px] text-emerald-700 font-bold block mt-2">
                        {m.course_ids.length} Courses • ~{m.estimated_hours} hrs
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Personalized Budget Breakdown & Model Comparison (Requirement 5) */}
          {currentPlan.budget_breakdown && (
            <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
                <div>
                  <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                    <DollarSign className="w-5 h-5 text-emerald-600" />
                    Personalized Budget Planning & Pricing Comparison
                  </h3>
                  <p className="text-xs text-slate-500">
                    Comparing free alternatives, one-time paid courses, and monthly subscription durations.
                  </p>
                </div>
                <div className="text-right">
                  <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${
                    currentPlan.budget_breakdown.is_within_budget 
                      ? 'bg-emerald-100 text-emerald-800' 
                      : 'bg-rose-100 text-rose-800'
                  }`}>
                    {currentPlan.budget_breakdown.is_within_budget ? 'Within Budget' : 'Exceeds Budget'}
                  </span>
                </div>
              </div>

              {currentPlan.budget_breakdown.staged_path_suggestion && (
                <div className="p-3 bg-emerald-50/80 border border-emerald-200 rounded-xl text-xs text-emerald-900 flex items-start gap-2">
                  <Info className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <div className="leading-relaxed">
                    <strong>Recommended Staged Strategy:</strong> {currentPlan.budget_breakdown.staged_path_suggestion}
                  </div>
                </div>
              )}

              {/* Model Comparisons Table */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
                {currentPlan.budget_breakdown.comparisons.map((c, i) => (
                  <div key={i} className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-xs flex flex-col justify-between">
                    <div>
                      <h4 className="font-bold text-slate-800 mb-1">{c.provider_summary}</h4>
                      <div className="text-lg font-bold text-slate-900 my-2">
                        ${c.estimated_cost.toFixed(2)}
                        {c.estimated_months > 0 && (
                          <span className="text-xs font-normal text-slate-500 ml-1">
                            (~{c.estimated_months} mos)
                          </span>
                        )}
                      </div>
                      <div className="space-y-1 text-slate-600 text-[11px]">
                        <p>Certificate Included: {c.certificate_included ? 'Yes ✅' : 'No / Separate'}</p>
                        {c.financial_assistance_available && (
                          <p className="text-emerald-700 font-semibold">Financial Aid: Available 🎓</p>
                        )}
                      </div>
                    </div>
                    {c.financial_assistance_details && (
                      <p className="mt-3 pt-2 border-t border-slate-200 text-[10px] text-slate-400">
                        {c.financial_assistance_details}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Sequenced Courses DAG Timeline (FR-04, Requirement 4 & 6) */}
          <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <GitFork className="w-5 h-5 text-emerald-600" />
              Recommended Course Sequence (Topological Kahn DAG)
            </h3>
            <p className="text-xs text-slate-500">
              Prerequisites are automatically prioritized before advanced concepts.
            </p>

            <div className="space-y-3">
              {currentPlan.ordered_courses.map((course, idx) => (
                <div 
                  key={course.course_id} 
                  className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-4 rounded-xl border border-slate-200 hover:border-emerald-300 hover:bg-slate-50/50 transition gap-4"
                >
                  <div className="flex items-start gap-3">
                    <div className="w-7 h-7 rounded-full bg-emerald-600 text-white font-bold text-xs flex items-center justify-center shrink-0 mt-0.5">
                      {idx + 1}
                    </div>
                    <div>
                      <div className="flex flex-wrap items-center gap-2 mb-1">
                        <span className="font-bold text-sm text-slate-900">{course.title}</span>
                        <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-medium">
                          {course.platform}
                        </span>
                        {course.is_foundation && (
                          <span className="text-[10px] bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full font-semibold">
                            Auto-Inserted Prerequisite
                          </span>
                        )}
                        <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
                          Level {course.level}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500">
                        Provider: <span className="font-medium text-slate-700">{course.provider}</span> • 
                        Duration: <span className="font-medium text-slate-700">{course.hours} hrs</span> • 
                        Cost: <span className="font-medium text-slate-700">${course.cost} ({course.pricing_model})</span>
                      </p>

                      {/* Credential Details (Requirement 6) */}
                      {course.certificate_info?.available && (
                        <div className="flex items-center gap-2 mt-2 text-[11px] text-amber-800 bg-amber-50/60 px-2.5 py-1 rounded-md border border-amber-200/50">
                          <Award className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                          <span>
                            <strong>Credential:</strong> {course.certificate_info.type.replace('_', ' ')} by {course.certificate_info.issuer}
                            {course.certificate_info.separate_certificate_fee > 0 && ` (+$${course.certificate_info.separate_certificate_fee} exam fee)`}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
                    {course.source_url && !course.source_url.includes('internal.corp') && (
                      <a
                        href={course.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold flex items-center gap-1 transition"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                        Platform Page
                      </a>
                    )}
                    <button
                      onClick={() => onNavigateToCourse(course.course_id)}
                      className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1 transition shadow-xs"
                    >
                      Study Module
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Responsible AI Disclaimer (Requirement 6 & FR-10) */}
          <div className="p-4 bg-slate-100 rounded-2xl border border-slate-200/80 text-xs text-slate-600 flex items-start gap-3">
            <ShieldAlert className="w-5 h-5 text-slate-400 shrink-0 mt-0.5" />
            <p className="leading-relaxed">
              <strong>Advisory Guardrail Disclaimer:</strong> {currentPlan.disclaimer}
            </p>
          </div>
        </>
      )}
    </div>
  );
};
