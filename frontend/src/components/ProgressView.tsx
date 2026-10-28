import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, 
  Award, 
  Clock, 
  CheckCircle2, 
  XCircle, 
  ShieldCheck, 
  AlertCircle,
  ArrowRight
} from 'lucide-react';
import { EmployeeProfile, AssessmentResult, LearningProgressItem, SkillGapItem, api } from '../lib/api';

interface ProgressViewProps {
  empId: string;
  onNavigateToCourse: (courseId: string) => void;
}

export const ProgressView: React.FC<ProgressViewProps> = ({ empId, onNavigateToCourse }) => {
  const [profile, setProfile] = useState<EmployeeProfile | null>(null);
  const [assessments, setAssessments] = useState<AssessmentResult[]>([]);
  const [progressItems, setProgressItems] = useState<LearningProgressItem[]>([]);
  const [gaps, setGaps] = useState<SkillGapItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadProgressData();
  }, [empId]);

  const loadProgressData = async () => {
    setLoading(true);
    try {
      const [profData, assessData, progData] = await Promise.all([
        api.getProfile(empId),
        api.getAssessments(empId),
        api.getProgress(empId)
      ]);
      setProfile(profData);
      setAssessments(assessData);
      setProgressItems(progData);

      if (profData.target_role) {
        const gapRes = await api.analyzeSkillGaps(empId, profData.target_role);
        setGaps(gapRes.gaps);
      }
    } catch (e) {
      console.error('Failed to load progress data:', e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
      </div>
    );
  }

  const totalMinutes = progressItems.reduce((acc, p) => acc + (p.time_spent_minutes || 0), 0);
  const completedLessons = progressItems.filter(p => p.status === 'completed').length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-slate-200">
        <h2 className="text-xl font-bold text-slate-800">Skills & Learning Progress</h2>
        <p className="text-xs text-slate-500 mt-1">
          Tracking demonstrated competencies, assessment audit trails, and remaining skill gaps for {profile?.target_role}.
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-1">
            <span className="text-xs font-medium">Completed Lessons</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-bold text-slate-800">{completedLessons}</div>
          <span className="text-[10px] text-slate-400">Recorded across active courses</span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-1">
            <span className="text-xs font-medium">Total Study Time</span>
            <Clock className="w-4 h-4 text-blue-600" />
          </div>
          <div className="text-2xl font-bold text-slate-800">{round1(totalMinutes / 60)} <span className="text-xs font-normal">hours</span></div>
          <span className="text-[10px] text-slate-400">{totalMinutes} minutes invested</span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 mb-1">
            <span className="text-xs font-medium">Rubric Assessments</span>
            <Award className="w-4 h-4 text-amber-600" />
          </div>
          <div className="text-2xl font-bold text-slate-800">{assessments.length}</div>
          <span className="text-[10px] text-slate-400">{assessments.filter(a => a.passed).length} successfully passed</span>
        </div>
      </div>

      {/* Skill Gaps Analysis: Current vs Target */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
        <div className="flex justify-between items-center">
          <div>
            <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-emerald-600" />
              Target Competencies vs Current Proficiency
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">Role target: {profile?.target_role}</p>
          </div>
        </div>

        <div className="space-y-4 pt-2">
          {gaps.length === 0 ? (
            <div className="text-center py-6 text-xs text-slate-500">
              No skill gaps detected! You meet or exceed all required proficiencies for this role.
            </div>
          ) : (
            gaps.map((item) => {
              const currentProf = item.current_proficiency;
              const targetProf = item.target_proficiency;
              const percent = Math.min(100, Math.round((currentProf / targetProf) * 100));

              return (
                <div key={item.skill} className="p-3.5 rounded-lg border border-slate-100 bg-slate-50/60 space-y-2">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-bold text-slate-800">{item.skill}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-slate-500">
                        Current: <strong className="text-emerald-700">{currentProf}/5</strong> • Target: <strong className="text-slate-800">{targetProf}/5</strong>
                      </span>
                      <span className="text-[11px] font-bold text-amber-700 bg-amber-100 px-2 py-0.5 rounded-md">
                        Gap: +{item.gap}
                      </span>
                    </div>
                  </div>

                  <div className="w-full bg-slate-200 rounded-full h-2.5 overflow-hidden">
                    <div 
                      className="bg-emerald-600 h-2.5 rounded-full transition-all duration-500" 
                      style={{ width: `${percent}%` }}
                    />
                  </div>

                  {item.recommended_course_ids.length > 0 && (
                    <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
                      <span>Recommended catalogue courses: <strong>{item.recommended_course_ids.join(', ')}</strong></span>
                      <button
                        onClick={() => onNavigateToCourse(item.recommended_course_ids[0])}
                        className="text-emerald-700 font-bold hover:underline inline-flex items-center gap-1"
                      >
                        Study Course <ArrowRight className="w-3 h-3" />
                      </button>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Assessment Audit History (FR-07) */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
        <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-blue-600" />
          Assessment Audit Trail & Evidence Records
        </h3>

        {assessments.length === 0 ? (
          <p className="text-xs text-slate-500">No standardized assessments submitted yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase font-semibold border-b border-slate-200">
                <tr>
                  <th className="py-2.5 px-3">Date</th>
                  <th className="py-2.5 px-3">Assessment ID</th>
                  <th className="py-2.5 px-3">Course / Skill</th>
                  <th className="py-2.5 px-3">Score</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Rubric Evidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {assessments.map((a, idx) => (
                  <tr key={idx} className="hover:bg-slate-50/70">
                    <td className="py-2.5 px-3 text-slate-400 whitespace-nowrap">
                      {a.created_at ? new Date(a.created_at).toLocaleDateString() : 'Recent'}
                    </td>
                    <td className="py-2.5 px-3 font-mono font-bold text-slate-700">{a.assessment_id}</td>
                    <td className="py-2.5 px-3 text-slate-800 font-medium">{a.course_id} ({a.skill_id})</td>
                    <td className="py-2.5 px-3 font-bold text-slate-800">{a.score}%</td>
                    <td className="py-2.5 px-3">
                      {a.passed ? (
                        <span className="inline-flex items-center gap-1 text-[11px] bg-emerald-100 text-emerald-800 font-semibold px-2 py-0.5 rounded-full">
                          <CheckCircle2 className="w-3 h-3" /> Passed
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[11px] bg-red-100 text-red-800 font-semibold px-2 py-0.5 rounded-full">
                          <XCircle className="w-3 h-3" /> Failed
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-slate-500 max-w-xs truncate" title={a.evidence}>
                      {a.evidence}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

function round1(val: number): number {
  return Math.round(val * 10) / 10;
}
