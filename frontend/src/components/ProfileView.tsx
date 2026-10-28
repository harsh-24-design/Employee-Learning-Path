import React, { useState, useEffect } from 'react';
import { 
  User, 
  Target, 
  Clock, 
  DollarSign, 
  Award, 
  Save, 
  CheckCircle2, 
  ShieldCheck, 
  Sparkles,
  Layers,
  AlertCircle,
  HelpCircle,
  Zap
} from 'lucide-react';
import { EmployeeProfile, Role, CertificateType, api } from '../lib/api';

interface ProfileViewProps {
  empId: string;
  onProfileUpdated: () => void;
}

export const ProfileView: React.FC<ProfileViewProps> = ({ empId, onProfileUpdated }) => {
  const [profile, setProfile] = useState<EmployeeProfile | null>(null);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  // Goal Mode: 'catalog_role' vs 'custom_goal'
  const [goalMode, setGoalMode] = useState<'catalog_role' | 'custom_goal'>('catalog_role');
  const [name, setName] = useState('');
  const [department, setDepartment] = useState('');
  const [targetRole, setTargetRole] = useState('Data Analyst');
  const [customGoalTitle, setCustomGoalTitle] = useState('Python & Modern Web Development');
  const [customGoalDesc, setCustomGoalDesc] = useState('Learning Python and API design for personal projects and career advancement.');
  
  // Preferences
  const [weeklyHours, setWeeklyHours] = useState(10);
  const [dailyHours, setDailyHours] = useState(1.5);
  const [learningStyle, setLearningStyle] = useState('mixed');
  const [intensity, setIntensity] = useState('normal');
  const [budget, setBudget] = useState(500);
  const [targetDate, setTargetDate] = useState('');
  const [wantsCert, setWantsCert] = useState(true);
  const [certType, setCertType] = useState<CertificateType>('professional_certificate');

  // Skills
  const [skillRatings, setSkillRatings] = useState<Record<string, number>>({});
  const [newSkillName, setNewSkillName] = useState('');
  const [newSkillLevel, setNewSkillLevel] = useState(2);

  useEffect(() => {
    loadData();
  }, [empId]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [profData, rolesData] = await Promise.all([
        api.getProfile(empId),
        api.getRoles()
      ]);
      setProfile(profData);
      setRoles(rolesData);

      setName(profData.name || '');
      setDepartment(profData.department || '');
      setTargetRole(profData.target_role || 'Data Analyst');
      setWeeklyHours(profData.preferences?.weekly_hours_available || 10);
      setDailyHours(profData.preferences?.daily_study_hours || 1.5);
      setLearningStyle(profData.preferences?.preferred_learning_style || 'mixed');
      setIntensity(profData.preferences?.training_intensity || 'normal');
      setBudget(profData.preferences?.budget_limit || 500);
      setTargetDate(profData.preferences?.target_completion_date || '');
      setWantsCert(profData.preferences?.wants_certificate ?? true);
      setCertType(profData.preferences?.preferred_certificate_type || 'professional_certificate');

      const initialSkills: Record<string, number> = {};
      profData.skills.forEach(s => {
        initialSkills[s.skill] = s.self_assessed_level;
      });
      setSkillRatings(initialSkills);
    } catch (e) {
      console.error('Failed to load profile:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleAddCustomSkill = () => {
    if (!newSkillName.trim()) return;
    setSkillRatings(prev => ({ ...prev, [newSkillName.trim()]: newSkillLevel }));
    setNewSkillName('');
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSavedSuccess(false);

    try {
      if (goalMode === 'custom_goal') {
        // Create custom goal directly
        await api.createCustomGoal({
          employee_id: empId,
          goal_title: customGoalTitle,
          goal_description: customGoalDesc,
          target_skills: skillRatings,
          budget: budget,
          weekly_hours: weeklyHours
        });
      }

      await api.updateProfile(empId, {
        name,
        department,
        target_role: goalMode === 'catalog_role' ? targetRole : customGoalTitle,
        preferences: {
          preferred_learning_style: learningStyle,
          daily_study_hours: dailyHours,
          weekly_hours_available: weeklyHours,
          training_intensity: intensity,
          budget_limit: budget,
          target_completion_date: targetDate || null,
          wants_certificate: wantsCert,
          preferred_certificate_type: certType
        },
        self_assessed_skills: skillRatings
      });

      // Regenerate plan with updated criteria
      if (goalMode === 'catalog_role') {
        await api.generateRoadmap(
          empId, 
          targetRole, 
          budget, 
          weeklyHours, 
          'self_directed', 
          intensity, 
          wantsCert
        );
      }

      setSavedSuccess(true);
      onProfileUpdated();
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (e) {
      console.error('Failed to update profile:', e);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
      </div>
    );
  }

  const isSelectedRoleInCatalog = roles.some(r => r.role_name.toLowerCase() === targetRole.toLowerCase());

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-4 border-b border-slate-200">
        <div>
          <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
            <User className="w-5 h-5 text-emerald-600" />
            Learning Profile & Career Goals
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Choose your learning mode, adjust personal study intensity & budget, and maintain your skill proficiencies.
          </p>
        </div>

        {savedSuccess && (
          <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-50 text-emerald-700 text-xs font-semibold rounded-lg border border-emerald-200 animate-fade-in">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            Profile and roadmap updated!
          </div>
        )}
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Goal Mode Selection (Requirement 2 & 3) */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
              <Target className="w-4 h-4 text-emerald-600" />
              1. Goal Selection Mode (Self-Directed Learning)
            </h3>
            <div className="flex bg-slate-100 p-0.5 rounded-lg text-xs">
              <button
                type="button"
                onClick={() => setGoalMode('catalog_role')}
                className={`px-3 py-1 rounded-md font-medium transition ${
                  goalMode === 'catalog_role' ? 'bg-white shadow-xs text-slate-900 font-bold' : 'text-slate-500'
                }`}
              >
                Target Career Role
              </button>
              <button
                type="button"
                onClick={() => setGoalMode('custom_goal')}
                className={`px-3 py-1 rounded-md font-medium transition ${
                  goalMode === 'custom_goal' ? 'bg-white shadow-xs text-slate-900 font-bold' : 'text-slate-500'
                }`}
              >
                Custom Skill / Topic Goal
              </button>
            </div>
          </div>

          {goalMode === 'catalog_role' ? (
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Select Target Role from Catalogue</label>
                <select
                  value={targetRole}
                  onChange={e => setTargetRole(e.target.value)}
                  className="w-full text-xs p-2.5 bg-slate-50 border border-slate-300 rounded-lg outline-none focus:ring-2 focus:ring-emerald-500"
                >
                  {roles.map(r => (
                    <option key={r.role_name} value={r.role_name}>
                      {r.role_name} ({r.competencies.length} competencies)
                    </option>
                  ))}
                  <option value="Custom / Unlisted Role">Other / Custom Target Role...</option>
                </select>
              </div>

              {!isSelectedRoleInCatalog && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold">Role-Specific Competency Data Unavailable:</span>
                    <p className="text-[11px] text-amber-700 mt-0.5">
                      This role does not have a predefined competency matrix in the role catalogue. The agent will assess your goals based on your individual skills and custom roadmap sequence.
                    </p>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-3 p-4 bg-emerald-50/40 border border-emerald-100 rounded-xl">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Custom Goal Title</label>
                <input
                  type="text"
                  value={customGoalTitle}
                  onChange={e => setCustomGoalTitle(e.target.value)}
                  placeholder="e.g. Learning Python for Personal Development"
                  className="w-full text-xs p-2.5 bg-white border border-slate-300 rounded-lg outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Goal Description & Motivation</label>
                <textarea
                  rows={2}
                  value={customGoalDesc}
                  onChange={e => setCustomGoalDesc(e.target.value)}
                  placeholder="Describe your learning objectives, interest area, or career motivation..."
                  className="w-full text-xs p-2 bg-white border border-slate-300 rounded-lg outline-none"
                />
              </div>
            </div>
          )}
        </div>

        {/* Study Preferences & Personal Budget (Requirement 5 & 7) */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
          <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
            <Clock className="w-4 h-4 text-blue-600" />
            2. Study Velocity, Training Intensity & Personal Budget
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Weekly Availability (Hours)</label>
              <input
                type="number"
                min="1"
                max="40"
                step="0.5"
                value={weeklyHours}
                onChange={e => setWeeklyHours(Number(e.target.value))}
                className="w-full text-xs p-2 bg-slate-50 border border-slate-300 rounded-lg outline-none"
              />
              <span className="text-[10px] text-slate-400 mt-1 block">
                {weeklyHours <= 3 ? '⚠️ Extended-timeline plan flag enabled' : 'Recommended: 8 - 15 hrs/week'}
              </span>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Training Intensity</label>
              <select
                value={intensity}
                onChange={e => setIntensity(e.target.value)}
                className="w-full text-xs p-2 bg-slate-50 border border-slate-300 rounded-lg outline-none"
              >
                <option value="light">Light Pace (0.8x velocity)</option>
                <option value="normal">Normal Pace (1.0x standard)</option>
                <option value="intensive">Intensive Bootcamp (1.3x accelerated)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Personal Learning Budget ($)</label>
              <input
                type="number"
                min="0"
                step="25"
                value={budget}
                onChange={e => setBudget(Number(e.target.value))}
                className="w-full text-xs p-2 bg-slate-50 border border-slate-300 rounded-lg outline-none"
              />
              <span className="text-[10px] text-slate-400 mt-1 block">
                {budget === 0 ? 'Zero-budget mode (100% free courses only)' : 'Total budget across all courses'}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Target Completion Date (Optional)</label>
              <input
                type="date"
                value={targetDate}
                onChange={e => setTargetDate(e.target.value)}
                className="w-full text-xs p-2 bg-slate-50 border border-slate-300 rounded-lg outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Preferred Learning Style</label>
              <select
                value={learningStyle}
                onChange={e => setLearningStyle(e.target.value)}
                className="w-full text-xs p-2 bg-slate-50 border border-slate-300 rounded-lg outline-none"
              >
                <option value="mixed">Mixed (Video, Reading & Applied Projects)</option>
                <option value="practice">Hands-On Practice & Coding Focused</option>
                <option value="video">Video Lectures & Structured Visuals</option>
                <option value="reading">Documentation & Case Studies</option>
              </select>
            </div>
          </div>
        </div>

        {/* Certificate & Credential Preferences (Requirement 6) */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
          <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
            <Award className="w-4 h-4 text-amber-600" />
            3. Certificate & Credential Recommendations
          </h3>

          <div className="flex items-center gap-2 mb-2">
            <input
              type="checkbox"
              id="wantsCert"
              checked={wantsCert}
              onChange={e => setWantsCert(e.target.checked)}
              className="rounded text-emerald-600 focus:ring-emerald-500"
            />
            <label htmlFor="wantsCert" className="text-xs font-semibold text-slate-800 cursor-pointer">
              I want verifiable certificates and credentials recommended in my roadmap
            </label>
          </div>

          {wantsCert && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Target Credential Type</label>
                <select
                  value={certType}
                  onChange={e => setCertType(e.target.value as CertificateType)}
                  className="w-full p-2 bg-white border border-slate-300 rounded-lg outline-none"
                >
                  <option value="completion_certificate">Course Completion Certificate (Udemy / Attendance)</option>
                  <option value="assessed_certificate">Assessed Course Certificate (Coursera / edX Exam)</option>
                  <option value="professional_certificate">Professional Certificate (Google / DeepLearning.AI)</option>
                  <option value="accredited_qualification">Accredited Academic Qualification</option>
                </select>
              </div>
              <div className="text-[11px] text-slate-500 flex items-center">
                The agent will prioritize platforms providing verified credentials and calculate any additional examination fees into your budget breakdown.
              </div>
            </div>
          )}
        </div>

        {/* Skills & Verified Assessments (Requirement 8) */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
            <div>
              <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                4. Demonstrated Skills & Self-Assessment
              </h3>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Self-reported levels are stored independently from assessment-verified proficiency (0 = None, 5 = Master).
              </p>
            </div>
          </div>

          {/* Current Skills Grid */}
          <div className="space-y-3">
            {profile?.skills.map(s => {
              const currentSelfRating = skillRatings[s.skill] ?? s.self_assessed_level;
              return (
                <div key={s.skill} className="flex flex-col sm:flex-row sm:items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-200/70 gap-3">
                  <div className="min-w-[160px]">
                    <span className="font-bold text-xs text-slate-800">{s.skill}</span>
                    <div className="flex items-center gap-2 mt-0.5">
                      {s.verified_level !== null ? (
                        <span className="text-[10px] font-semibold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full flex items-center gap-1">
                          <ShieldCheck className="w-3 h-3 text-emerald-600" />
                          Verified: Lvl {s.verified_level}
                        </span>
                      ) : (
                        <span className="text-[10px] text-slate-400">Not verified by assessment</span>
                      )}
                    </div>
                  </div>

                  <div className="flex-1 flex items-center gap-3">
                    <span className="text-xs text-slate-500 w-24">Self-Rating:</span>
                    <input
                      type="range"
                      min="0"
                      max="5"
                      value={currentSelfRating}
                      onChange={e => {
                        const val = Number(e.target.value);
                        setSkillRatings(prev => ({ ...prev, [s.skill]: val }));
                      }}
                      className="flex-1 accent-emerald-600 cursor-pointer"
                    />
                    <span className="font-bold text-xs text-slate-800 w-8 text-right">
                      {currentSelfRating}/5
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Add Custom Skill */}
          <div className="p-3 bg-slate-50/70 border border-dashed border-slate-300 rounded-xl flex flex-col sm:flex-row items-center gap-2">
            <input
              type="text"
              placeholder="Add another skill (e.g., Docker, FastAPI, Tableau)..."
              value={newSkillName}
              onChange={e => setNewSkillName(e.target.value)}
              className="text-xs px-3 py-2 bg-white border border-slate-300 rounded-lg flex-1 outline-none w-full sm:w-auto"
            />
            <div className="flex items-center gap-2 w-full sm:w-auto">
              <span className="text-xs text-slate-500">Level:</span>
              <select
                value={newSkillLevel}
                onChange={e => setNewSkillLevel(Number(e.target.value))}
                className="text-xs p-2 bg-white border border-slate-300 rounded-lg outline-none"
              >
                {[0, 1, 2, 3, 4, 5].map(lvl => (
                  <option key={lvl} value={lvl}>{lvl} - {['Novice', 'Beginner', 'Intermediate', 'Proficient', 'Advanced', 'Master'][lvl]}</option>
                ))}
              </select>
              <button
                type="button"
                onClick={handleAddCustomSkill}
                className="px-3 py-2 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-xs font-semibold whitespace-nowrap"
              >
                Add Skill
              </button>
            </div>
          </div>
        </div>

        {/* Submit */}
        <div className="flex justify-end gap-3 pt-2">
          <button
            type="submit"
            disabled={saving}
            className="flex items-center gap-2 px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition shadow-sm"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Updating & Regenerating Plan...' : 'Save Profile & Generate Roadmap'}
          </button>
        </div>
      </form>
    </div>
  );
};
