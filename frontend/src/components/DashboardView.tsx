import React from 'react';
import { 
  BookOpen, 
  CheckCircle2, 
  Clock, 
  TrendingUp, 
  ArrowRight, 
  Award, 
  Sparkles, 
  AlertCircle,
  PlayCircle
} from 'lucide-react';
import { DashboardResponse } from '../lib/api';

interface DashboardViewProps {
  data: DashboardResponse | null;
  loading: boolean;
  onNavigate: (tab: string, context?: any) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({ data, loading, onNavigate }) => {
  if (loading || !data) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-emerald-600"></div>
      </div>
    );
  }

  const { employee, active_courses_count, completed_courses_count, overall_progress_percent, study_hours_this_week, next_recommended_task, recent_activity, active_plan, skill_summary } = data;

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-gradient-to-r from-emerald-700 via-teal-700 to-slate-800 rounded-2xl p-6 text-white shadow-sm flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold uppercase tracking-wider bg-emerald-500/20 text-emerald-200 px-2.5 py-0.5 rounded-full border border-emerald-400/30">
              {employee.department}
            </span>
            <span className="text-xs text-slate-300">ID: {employee.employee_id}</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">Welcome back, {employee.name}</h1>
          <p className="text-slate-200 text-sm mt-1">
            Current Target Role: <span className="font-semibold text-emerald-200">{employee.target_role || 'Not set'}</span> • {employee.preferences?.weekly_hours_available || 10} hrs/week planned
          </p>
        </div>
        <div className="flex gap-2">
          <button 
            onClick={() => onNavigate('assistant')}
            className="flex items-center gap-1.5 px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-lg text-sm font-medium transition backdrop-blur-sm border border-white/10"
          >
            <Sparkles className="w-4 h-4 text-emerald-300" />
            Ask AI Advisor
          </button>
          <button 
            onClick={() => onNavigate('roadmap')}
            className="flex items-center gap-1.5 px-4 py-2 bg-emerald-500 hover:bg-emerald-400 text-slate-900 rounded-lg text-sm font-semibold transition shadow"
          >
            View Roadmap
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-xl border border-slate-200/80 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Overall Progress</span>
            <TrendingUp className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-bold text-slate-800">{overall_progress_percent}%</div>
          <div className="w-full bg-slate-100 rounded-full h-2 mt-3 overflow-hidden">
            <div 
              className="bg-emerald-600 h-2 rounded-full transition-all duration-500" 
              style={{ width: `${Math.min(100, Math.max(5, overall_progress_percent))}%` }}
            />
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200/80 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Active Path Courses</span>
            <BookOpen className="w-4 h-4 text-blue-600" />
          </div>
          <div className="text-2xl font-bold text-slate-800">{active_courses_count}</div>
          <p className="text-xs text-slate-500 mt-2">Planned in roadmap</p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200/80 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Completed Courses</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-bold text-slate-800">{completed_courses_count}</div>
          <p className="text-xs text-slate-500 mt-2">Verified completed</p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200/80 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Study Time Tracked</span>
            <Clock className="w-4 h-4 text-amber-600" />
          </div>
          <div className="text-2xl font-bold text-slate-800">{study_hours_this_week} <span className="text-sm font-normal text-slate-500">hrs</span></div>
          <p className="text-xs text-slate-500 mt-2">Recorded study time</p>
        </div>
      </div>

      {/* Main Grid: Next Task & Skills Snapshot */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2 spans): Next Task & Plan Highlight */}
        <div className="lg:col-span-2 space-y-6">
          {/* Actionable Next Recommended Task */}
          {next_recommended_task ? (
            <div className="bg-emerald-50/70 border border-emerald-200 rounded-xl p-5 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <span className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-800 uppercase tracking-wide bg-emerald-100/80 px-2.5 py-1 rounded-md">
                  <PlayCircle className="w-3.5 h-3.5" />
                  Next Recommended Action
                </span>
                <span className="text-xs text-emerald-700 font-medium">{next_recommended_task.hours} hrs est.</span>
              </div>
              <h3 className="text-lg font-bold text-slate-900">{next_recommended_task.title} ({next_recommended_task.course_id})</h3>
              <p className="text-sm text-slate-600 mt-1 mb-4">
                Skill focus: <span className="font-semibold text-slate-800">{next_recommended_task.skill}</span>. Complete modular lessons and take the assessment to upgrade verified proficiency.
              </p>
              <button
                onClick={() => onNavigate('learning', { course_id: next_recommended_task.course_id })}
                className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium rounded-lg transition shadow-sm"
              >
                Go to Course Workspace
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="bg-slate-50 border border-slate-200 rounded-xl p-6 text-center">
              <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
              <h3 className="text-sm font-bold text-slate-800">All current roadmap courses completed!</h3>
              <p className="text-xs text-slate-500 mt-1">Generate a new target roadmap or explore advanced electives.</p>
            </div>
          )}

          {/* Active Roadmap & Dual-Mode Cards */}
          <div className="space-y-4">
            {data.self_directed_plan && (
              <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <span className="text-[10px] font-bold text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded-full uppercase">
                      Personal Self-Directed Goal
                    </span>
                    <h3 className="font-bold text-slate-900 text-sm mt-1">{data.self_directed_plan.target_role}</h3>
                  </div>
                  <span className="text-xs font-semibold px-2.5 py-1 bg-slate-100 text-slate-700 rounded-full">
                    {data.self_directed_plan.estimated_weeks} weeks • ${data.self_directed_plan.total_cost.toFixed(2)}
                  </span>
                </div>
                <div className="text-xs text-slate-500 flex justify-between items-center">
                  <span>{data.self_directed_plan.ordered_courses.length} courses planned ({data.self_directed_plan.weekly_hours} hrs/wk)</span>
                  <button onClick={() => onNavigate('roadmap')} className="text-emerald-700 font-semibold hover:underline">
                    View Roadmap →
                  </button>
                </div>
              </div>
            )}

            {data.company_assigned_plan && (
              <div className="bg-blue-50/70 border border-blue-200 rounded-xl p-5 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <span className="text-[10px] font-bold text-blue-800 bg-blue-100 px-2 py-0.5 rounded-full uppercase">
                      🏢 Company-Assigned Track
                    </span>
                    <h3 className="font-bold text-blue-900 text-sm mt-1">{data.company_assigned_plan.target_role}</h3>
                  </div>
                  <span className="text-xs font-semibold px-2.5 py-1 bg-blue-100 text-blue-800 rounded-full">
                    Deadline: {data.company_assigned_plan.assignment_deadline || 'Open'}
                  </span>
                </div>
                <p className="text-xs text-blue-700 mb-2">
                  Assigned by {data.company_assigned_plan.assigned_by || 'Manager'}: {data.company_assigned_plan.manager_notes}
                </p>
                <div className="text-xs text-blue-800 flex justify-between items-center">
                  <span>{data.company_assigned_plan.ordered_courses.length} required courses • Corporate Budget: ${data.company_assigned_plan.budget_limit}</span>
                  <button onClick={() => onNavigate('roadmap')} className="text-blue-800 font-bold hover:underline">
                    View Assigned Plan →
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Column (1 span): Skills Overview & Recent Activities */}
        <div className="space-y-6">
          {/* Skills Breakdown */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
            <h3 className="font-bold text-slate-800 mb-1 flex items-center gap-2">
              <Award className="w-4 h-4 text-emerald-600" />
              Skill Proficiency Status
            </h3>
            <p className="text-xs text-slate-500 mb-4">Comparing self-rating vs rubric-verified levels (0–5)</p>

            <div className="space-y-3">
              {skill_summary.map((sk) => (
                <div key={sk.skill} className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="font-semibold text-slate-700">{sk.skill}</span>
                    <span className="text-slate-500">
                      Self: <strong className="text-slate-800">{sk.self}</strong> | Verified: <strong className="text-emerald-700">{sk.verified}</strong>/5
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-1 h-2 rounded bg-slate-100 overflow-hidden">
                    <div 
                      className="bg-blue-400 h-full rounded-l" 
                      style={{ width: `${(sk.self / 5) * 100}%` }} 
                      title={`Self-Assessed: ${sk.self}/5`}
                    />
                    <div 
                      className="bg-emerald-600 h-full rounded-r" 
                      style={{ width: `${(sk.verified / 5) * 100}%` }} 
                      title={`Verified: ${sk.verified}/5`}
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-between text-[11px] text-slate-500 mt-4 pt-3 border-t border-slate-100">
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-blue-400"></span> Self-Assessed</span>
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-emerald-600"></span> Rubric-Verified</span>
            </div>
          </div>

          {/* Recent Activity Feed */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
            <h3 className="font-bold text-slate-800 mb-3 text-sm">Recent Activity</h3>
            {recent_activity.length === 0 ? (
              <p className="text-xs text-slate-500">No recorded learning activity yet.</p>
            ) : (
              <div className="space-y-3">
                {recent_activity.map((act, i) => (
                  <div key={i} className="text-xs pb-2 border-b border-slate-100 last:border-0 last:pb-0">
                    <p className="text-slate-700 font-medium">{act.description}</p>
                    <span className="text-[10px] text-slate-400">
                      {act.timestamp ? new Date(act.timestamp).toLocaleString() : 'Just now'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
