import React, { useState, useEffect } from 'react';
import { 
  Users, 
  Calendar, 
  DollarSign, 
  Clock, 
  CheckCircle2, 
  AlertCircle, 
  PlusCircle, 
  TrendingUp, 
  ShieldCheck,
  Send
} from 'lucide-react';
import { TeamMemberSummary, Role, api } from '../lib/api';

export const ManagerTeamView: React.FC = () => {
  const [team, setTeam] = useState<TeamMemberSummary[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [selectedEmp, setSelectedEmp] = useState<TeamMemberSummary | null>(null);

  // Form states for assignment
  const [targetRole, setTargetRole] = useState('Data Analyst');
  const [deadline, setDeadline] = useState('2026-12-31');
  const [budget, setBudget] = useState(500);
  const [weeklyHours, setWeeklyHours] = useState(10);
  const [managerNotes, setManagerNotes] = useState('Required corporate upskilling track for Q4 milestone.');
  const [submitting, setSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [teamData, rolesData] = await Promise.all([
        api.getTeamOverview(),
        api.getRoles()
      ]);
      setTeam(teamData);
      setRoles(rolesData);
      if (rolesData.length > 0) {
        setTargetRole(rolesData[0].role_name);
      }
    } catch (e) {
      console.error('Failed to load team data:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenAssignModal = (member: TeamMemberSummary) => {
    setSelectedEmp(member);
    setAssignModalOpen(true);
    setSuccessMessage(null);
  };

  const handleAssignGoal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedEmp) return;

    setSubmitting(true);
    try {
      await api.assignCompanyGoal({
        employee_id: selectedEmp.employee_id,
        target_role: targetRole,
        assignment_deadline: deadline,
        budget: budget,
        weekly_hours: weeklyHours,
        manager_notes: managerNotes
      });
      setSuccessMessage(`Company goal '${targetRole}' successfully assigned to ${selectedEmp.name}.`);
      setAssignModalOpen(false);
      loadData();
    } catch (e) {
      console.error('Failed to assign company goal:', e);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-bold text-blue-800 bg-blue-100 px-2.5 py-0.5 rounded-full flex items-center gap-1">
              <Users className="w-3.5 h-3.5" /> Manager Portal
            </span>
            <span className="text-xs text-slate-500">Authorized Team Oversight</span>
          </div>
          <h2 className="text-2xl font-bold text-slate-900">Team Learning & Goal Assignments</h2>
          <p className="text-xs text-slate-500 mt-1">
            Assign company-sponsored learning requirements, set deadlines & corporate budgets, and track progress percentages.
          </p>
        </div>
      </div>

      {successMessage && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          {successMessage}
        </div>
      )}

      {/* Notice Banner */}
      <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl text-xs text-blue-900 flex items-start gap-3">
        <ShieldCheck className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold mb-0.5">Dual-Mode Separation Policy</p>
          <p className="text-blue-700 leading-relaxed">
            Company-assigned goals and corporate progress tracking are strictly separated from employees' personal self-directed learning goals. Employees can pursue personal interests independently without manager oversight into their personal roadmaps.
          </p>
        </div>
      </div>

      {/* Team Member Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {team.map((member) => (
          <div key={member.employee_id} className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm hover:shadow transition flex flex-col justify-between">
            <div>
              <div className="flex justify-between items-start mb-3">
                <div>
                  <h3 className="font-bold text-slate-900 text-sm">{member.name}</h3>
                  <p className="text-xs text-slate-500">{member.department} • ID: {member.employee_id}</p>
                  <p className="text-[11px] text-slate-400">{member.email}</p>
                </div>
                {member.has_active_assigned_plan ? (
                  <span className="text-[10px] font-semibold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full">
                    Active Assignment
                  </span>
                ) : (
                  <span className="text-[10px] font-semibold bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">
                    No Company Goal
                  </span>
                )}
              </div>

              {member.has_active_assigned_plan ? (
                <div className="space-y-3 mt-4 pt-3 border-t border-slate-100">
                  <div className="text-xs">
                    <span className="text-slate-500">Assigned Goal:</span>
                    <span className="font-bold text-slate-800 ml-1.5">{member.assigned_role}</span>
                  </div>

                  <div className="flex justify-between text-xs text-slate-600">
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5 text-slate-400" /> Deadline:
                    </span>
                    <span className="font-semibold text-slate-800">{member.assigned_deadline || 'No deadline'}</span>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-500">Assigned Progress</span>
                      <span className="font-bold text-emerald-700">{member.assigned_progress_percent}%</span>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                      <div 
                        className="bg-emerald-600 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${Math.min(100, Math.max(5, member.assigned_progress_percent))}%` }}
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <div className="py-6 text-center text-xs text-slate-400 border-t border-slate-100 mt-4">
                  Currently engaged in independent self-directed learning.
                </div>
              )}
            </div>

            <div className="mt-5 pt-3 border-t border-slate-100">
              <button
                onClick={() => handleOpenAssignModal(member)}
                className="w-full py-2 px-3 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition"
              >
                <PlusCircle className="w-4 h-4 text-emerald-400" />
                {member.has_active_assigned_plan ? 'Update Company Goal' : 'Assign Company Goal'}
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Assignment Modal */}
      {assignModalOpen && selectedEmp && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl border border-slate-200">
            <div className="flex justify-between items-center mb-4 pb-3 border-b border-slate-100">
              <div>
                <h3 className="text-base font-bold text-slate-900">Assign Company Goal</h3>
                <p className="text-xs text-slate-500">Employee: {selectedEmp.name} ({selectedEmp.employee_id})</p>
              </div>
              <button
                onClick={() => setAssignModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleAssignGoal} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Target Role / Track</label>
                <select
                  value={targetRole}
                  onChange={e => setTargetRole(e.target.value)}
                  className="w-full text-xs p-2.5 bg-slate-50 border border-slate-300 rounded-lg outline-none focus:ring-2 focus:ring-emerald-500"
                >
                  {roles.map(r => (
                    <option key={r.role_name} value={r.role_name}>{r.role_name}</option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Target Deadline</label>
                  <input
                    type="date"
                    value={deadline}
                    onChange={e => setDeadline(e.target.value)}
                    required
                    className="w-full text-xs p-2 bg-slate-50 border border-slate-300 rounded-lg outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Corporate Budget ($)</label>
                  <input
                    type="number"
                    min="0"
                    step="50"
                    value={budget}
                    onChange={e => setBudget(Number(e.target.value))}
                    className="w-full text-xs p-2 bg-slate-50 border border-slate-300 rounded-lg outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Allocated Weekly Study Hours</label>
                <input
                  type="number"
                  min="2"
                  max="25"
                  value={weeklyHours}
                  onChange={e => setWeeklyHours(Number(e.target.value))}
                  className="w-full text-xs p-2 bg-slate-50 border border-slate-300 rounded-lg outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Manager Notes / Justification</label>
                <textarea
                  rows={2}
                  value={managerNotes}
                  onChange={e => setManagerNotes(e.target.value)}
                  placeholder="e.g. Critical training for upcoming project delivery..."
                  className="w-full text-xs p-2 bg-slate-50 border border-slate-300 rounded-lg outline-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setAssignModalOpen(false)}
                  className="px-4 py-2 bg-slate-100 text-slate-700 text-xs font-semibold rounded-lg hover:bg-slate-200 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 transition"
                >
                  <Send className="w-3.5 h-3.5" />
                  {submitting ? 'Assigning...' : 'Confirm Assignment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
