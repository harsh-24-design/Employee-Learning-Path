import React, { useState, useEffect } from 'react';
import { 
  Database, 
  Search, 
  Upload, 
  CheckCircle2, 
  AlertCircle, 
  ExternalLink,
  BookOpen,
  Award,
  Layers,
  Filter,
  ShieldCheck,
  PlusCircle,
  FileCheck,
  Calendar
} from 'lucide-react';
import { Course, Role, RoleCompetency, CertificateType, api } from '../lib/api';

interface AdminCatalogViewProps {
  isAdmin?: boolean;
  onNavigateToCourse?: (courseId: string) => void;
}

export const AdminCatalogView: React.FC<AdminCatalogViewProps> = ({ isAdmin = false, onNavigateToCourse }) => {
  const [activeSubTab, setActiveSubTab] = useState<'courses' | 'roles'>('courses');
  
  // Courses state
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedPlatform, setSelectedPlatform] = useState('All');
  const [selectedPricing, setSelectedPricing] = useState('All');
  const [selectedCert, setSelectedCert] = useState('All');
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [importNotice, setImportNotice] = useState<string | null>(null);

  // Roles state (for Admin)
  const [roles, setRoles] = useState<Role[]>([]);
  const [roleModalOpen, setRoleModalOpen] = useState(false);
  const [newRoleName, setNewRoleName] = useState('');
  const [newRoleDesc, setNewRoleDesc] = useState('');
  const [newPrereqs, setNewPrereqs] = useState('');
  const [newResources, setNewResources] = useState('');
  const [newCompetencies, setNewCompetencies] = useState<{ skill: string; required_proficiency: number }[]>([
    { skill: 'Python', required_proficiency: 3 },
    { skill: 'SQL', required_proficiency: 2 }
  ]);
  const [roleSuccessNotice, setRoleSuccessNotice] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [coursesData, rolesData] = await Promise.all([
        api.discoverCourses({}),
        api.getRoles()
      ]);
      setCourses(coursesData);
      setRoles(rolesData);
    } catch (e) {
      console.error('Failed to load catalogue and roles:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleTriggerImport = async () => {
    setImporting(true);
    setImportNotice(null);
    try {
      const res = await api.triggerImport();
      setImportNotice(`Data re-sync successful: ${res.total_records} records imported.`);
      loadData();
    } catch (e) {
      setImportNotice('Failed to re-sync data sources.');
    } finally {
      setImporting(false);
    }
  };

  const handleCreateRole = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRoleName.trim()) return;

    try {
      await api.createRole({
        role_name: newRoleName.trim(),
        description: newRoleDesc.trim(),
        prerequisites: newPrereqs.split(',').map(s => s.trim()).filter(Boolean),
        relevant_resources: newResources.split(',').map(s => s.trim()).filter(Boolean),
        competencies: newCompetencies.filter(c => c.skill.trim())
      });
      setRoleSuccessNotice(`Role '${newRoleName}' successfully created!`);
      setRoleModalOpen(false);
      setNewRoleName('');
      setNewRoleDesc('');
      loadData();
    } catch (err: any) {
      alert(err.message || 'Failed to create role');
    }
  };

  const filteredCourses = courses.filter(c => {
    const matchesPlatform = selectedPlatform === 'All' || c.platform.toLowerCase() === selectedPlatform.toLowerCase();
    const matchesPricing = selectedPricing === 'All' || c.pricing_model.toLowerCase() === selectedPricing.toLowerCase();
    const matchesCert = selectedCert === 'All' || c.certificate_info?.type === selectedCert;
    const matchesSearch = !searchTerm || 
      c.title.toLowerCase().includes(searchTerm.toLowerCase()) || 
      c.skill.toLowerCase().includes(searchTerm.toLowerCase()) || 
      c.provider.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.course_id.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesPlatform && matchesPricing && matchesCert && matchesSearch;
  });

  const platforms = ['All', 'Internal', 'Coursera', 'edX', 'Udemy', 'freeCodeCamp'];

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-bold text-emerald-800 bg-emerald-100 px-2.5 py-0.5 rounded-full flex items-center gap-1">
              <Database className="w-3.5 h-3.5" /> Multi-Platform Catalogue
            </span>
            <span className="text-xs text-slate-500">Verified Internal & External Providers</span>
          </div>
          <h2 className="text-2xl font-bold text-slate-900">Course Discovery & Competency Management</h2>
          <p className="text-xs text-slate-500 mt-1">
            Explore approved courses across Coursera, edX, Udemy, freeCodeCamp, compare credential options, and review role competencies.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {isAdmin && (
            <button
              onClick={() => setRoleModalOpen(true)}
              className="flex items-center gap-1.5 px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold transition shadow-xs"
            >
              <PlusCircle className="w-3.5 h-3.5" />
              Add New Role
            </button>
          )}
          <button
            onClick={handleTriggerImport}
            disabled={importing}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-xs font-semibold transition shadow-xs"
          >
            <Upload className={`w-3.5 h-3.5 ${importing ? 'animate-bounce' : ''}`} />
            {importing ? 'Re-syncing...' : 'Re-sync Data'}
          </button>
        </div>
      </div>

      {importNotice && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          {importNotice}
        </div>
      )}

      {roleSuccessNotice && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          {roleSuccessNotice}
        </div>
      )}

      {/* Sub Tabs: Courses vs Roles */}
      <div className="flex space-x-2 border-b border-slate-200">
        <button
          onClick={() => setActiveSubTab('courses')}
          className={`pb-2.5 px-3 text-xs font-bold border-b-2 transition ${
            activeSubTab === 'courses' 
              ? 'border-emerald-600 text-emerald-700' 
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          Courses Explorer ({filteredCourses.length})
        </button>
        <button
          onClick={() => setActiveSubTab('roles')}
          className={`pb-2.5 px-3 text-xs font-bold border-b-2 transition ${
            activeSubTab === 'roles' 
              ? 'border-emerald-600 text-emerald-700' 
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          Role Competency Matrix ({roles.length} roles)
        </button>
      </div>

      {/* Courses Tab View */}
      {activeSubTab === 'courses' && (
        <div className="space-y-4">
          {/* Filters Bar */}
          <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search courses, skills, or providers (e.g. Python, Coursera, Google, SQL)..."
                  value={searchTerm}
                  onChange={e => setSearchTerm(e.target.value)}
                  className="w-full text-xs pl-9 pr-4 py-2 bg-slate-50 border border-slate-300 rounded-lg outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div className="flex gap-2">
                <select
                  value={selectedPricing}
                  onChange={e => setSelectedPricing(e.target.value)}
                  className="text-xs p-2 bg-slate-50 border border-slate-300 rounded-lg outline-none"
                >
                  <option value="All">All Pricing Models</option>
                  <option value="free">100% Free / Audit</option>
                  <option value="paid_one_time">Paid One-Time</option>
                  <option value="subscription">Subscription</option>
                </select>

                <select
                  value={selectedCert}
                  onChange={e => setSelectedCert(e.target.value)}
                  className="text-xs p-2 bg-slate-50 border border-slate-300 rounded-lg outline-none"
                >
                  <option value="All">All Credentials</option>
                  <option value="completion_certificate">Completion Certificate</option>
                  <option value="assessed_certificate">Assessed Certificate</option>
                  <option value="professional_certificate">Professional Certificate</option>
                </select>
              </div>
            </div>

            {/* Platform Filter Chips */}
            <div className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="text-[11px] font-semibold text-slate-400 mr-1 flex items-center gap-1">
                <Filter className="w-3 h-3" /> Platform:
              </span>
              {platforms.map(p => (
                <button
                  key={p}
                  onClick={() => setSelectedPlatform(p)}
                  className={`text-xs px-2.5 py-1 rounded-md font-medium transition ${
                    selectedPlatform === p
                      ? 'bg-emerald-600 text-white font-bold'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          {/* Courses Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredCourses.map(course => (
              <div 
                key={course.course_id}
                className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs hover:shadow transition flex flex-col justify-between"
              >
                <div>
                  <div className="flex justify-between items-start gap-2 mb-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider bg-slate-100 text-slate-700 px-2 py-0.5 rounded">
                      {course.platform}
                    </span>
                    <span className="text-[10px] font-semibold text-slate-500">
                      Lvl {course.level} • {course.hours} hrs
                    </span>
                  </div>

                  <h3 className="font-bold text-sm text-slate-900 mb-1 leading-snug">{course.title}</h3>
                  <p className="text-xs text-slate-500 mb-2">Provider: <span className="font-semibold text-slate-700">{course.provider}</span></p>

                  {course.description && (
                    <p className="text-xs text-slate-600 line-clamp-2 mb-3 leading-relaxed">
                      {course.description}
                    </p>
                  )}

                  <div className="flex flex-wrap items-center gap-2 mb-3">
                    <span className="text-[10px] bg-emerald-50 text-emerald-800 px-2 py-0.5 rounded font-medium border border-emerald-200">
                      Skill: {course.skill}
                    </span>
                    <span className="text-[10px] bg-blue-50 text-blue-800 px-2 py-0.5 rounded font-medium border border-blue-200">
                      {course.pricing_model === 'free' ? 'Free Course' : `$${course.cost} (${course.pricing_model})`}
                    </span>
                  </div>

                  {/* Certificate Info (Requirement 6) */}
                  {course.certificate_info?.available && (
                    <div className="p-2.5 bg-amber-50/70 rounded-lg border border-amber-200 text-xs text-amber-900 mb-3">
                      <div className="flex items-center gap-1.5 font-bold mb-0.5">
                        <Award className="w-3.5 h-3.5 text-amber-600" />
                        <span>{course.certificate_info.type.replace('_', ' ')}</span>
                      </div>
                      <p className="text-[11px] text-amber-800">
                        Issuer: {course.certificate_info.issuer}
                        {course.certificate_info.separate_certificate_fee > 0 && ` (+$${course.certificate_info.separate_certificate_fee} exam fee)`}
                      </p>
                    </div>
                  )}
                </div>

                <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs gap-2">
                  <span className={`text-[10px] font-semibold flex items-center gap-1 ${
                    course.source_verification_status === 'verified' ? 'text-emerald-700' : 'text-amber-700'
                  }`}>
                    <ShieldCheck className="w-3.5 h-3.5" />
                    {course.source_verification_status === 'verified' ? 'Verified Source' : 'Unconfirmed'}
                    {course.last_checked_date && ` (${course.last_checked_date})`}
                  </span>

                  <div className="flex items-center gap-1.5">
                    {onNavigateToCourse && (
                      <button
                        onClick={() => onNavigateToCourse(course.course_id)}
                        className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded text-[11px] transition flex items-center gap-1 shadow-2xs"
                      >
                        Study Course
                      </button>
                    )}
                    {course.source_url && !course.source_url.includes('internal.corp') && (
                      <a
                        href={course.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs font-semibold text-emerald-700 hover:text-emerald-900 flex items-center gap-1"
                      >
                        Official Page
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Role Competency Matrix Tab View (Requirement 3 & 10) */}
      {activeSubTab === 'roles' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {roles.map(role => (
              <div key={role.role_name} className="bg-white p-5 rounded-xl border border-slate-200 shadow-xs">
                <div className="flex justify-between items-start mb-2">
                  <h3 className="font-bold text-base text-slate-900">{role.role_name}</h3>
                  <span className="text-xs font-semibold bg-emerald-50 text-emerald-800 px-2 py-0.5 rounded-full border border-emerald-200">
                    {role.competencies.length} Target Competencies
                  </span>
                </div>
                <p className="text-xs text-slate-600 mb-4">{role.description}</p>

                {role.prerequisites && role.prerequisites.length > 0 && (
                  <div className="mb-3 text-xs">
                    <span className="font-semibold text-slate-500">Prerequisites:</span>
                    <span className="text-slate-700 ml-1.5">{role.prerequisites.join(', ')}</span>
                  </div>
                )}

                <div className="space-y-2 pt-2 border-t border-slate-100">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Required Competencies & Expected Proficiency
                  </span>
                  <div className="grid grid-cols-2 gap-2">
                    {role.competencies.map(c => (
                      <div key={c.skill} className="flex justify-between items-center p-2 bg-slate-50 rounded-lg text-xs">
                        <span className="font-medium text-slate-800">{c.skill}</span>
                        <span className="font-bold text-emerald-700">Lvl {c.required_proficiency}/5</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Add Role Modal (Admin) */}
      {roleModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200">
            <div className="flex justify-between items-center mb-4 pb-3 border-b border-slate-100">
              <h3 className="text-base font-bold text-slate-900">Add New Role Definition</h3>
              <button onClick={() => setRoleModalOpen(false)} className="text-slate-400 hover:text-slate-600">✕</button>
            </div>

            <form onSubmit={handleCreateRole} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Role Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. AI Prompt Engineer / Cloud Security Architect"
                  value={newRoleName}
                  onChange={e => setNewRoleName(e.target.value)}
                  className="w-full text-xs p-2 bg-slate-50 border border-slate-300 rounded-lg outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Description</label>
                <textarea
                  rows={2}
                  required
                  placeholder="Role responsibilities and competency benchmarks..."
                  value={newRoleDesc}
                  onChange={e => setNewRoleDesc(e.target.value)}
                  className="w-full text-xs p-2 bg-slate-50 border border-slate-300 rounded-lg outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Prerequisites (comma-separated)</label>
                <input
                  type="text"
                  placeholder="e.g. Python, Basic Linux"
                  value={newPrereqs}
                  onChange={e => setNewPrereqs(e.target.value)}
                  className="w-full text-xs p-2 bg-slate-50 border border-slate-300 rounded-lg outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Target Competencies</label>
                <div className="space-y-2">
                  {newCompetencies.map((comp, idx) => (
                    <div key={idx} className="flex gap-2">
                      <input
                        type="text"
                        placeholder="Skill name"
                        value={comp.skill}
                        onChange={e => {
                          const updated = [...newCompetencies];
                          updated[idx].skill = e.target.value;
                          setNewCompetencies(updated);
                        }}
                        className="flex-1 text-xs p-2 bg-slate-50 border border-slate-300 rounded-lg outline-none"
                      />
                      <select
                        value={comp.required_proficiency}
                        onChange={e => {
                          const updated = [...newCompetencies];
                          updated[idx].required_proficiency = Number(e.target.value);
                          setNewCompetencies(updated);
                        }}
                        className="text-xs p-2 bg-slate-50 border border-slate-300 rounded-lg outline-none"
                      >
                        {[1, 2, 3, 4, 5].map(l => (
                          <option key={l} value={l}>Level {l}</option>
                        ))}
                      </select>
                    </div>
                  ))}
                  <button
                    type="button"
                    onClick={() => setNewCompetencies([...newCompetencies, { skill: '', required_proficiency: 2 }])}
                    className="text-xs text-emerald-700 font-semibold hover:underline"
                  >
                    + Add Another Competency
                  </button>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setRoleModalOpen(false)}
                  className="px-4 py-2 bg-slate-100 text-slate-700 text-xs font-semibold rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg"
                >
                  Save Role Definition
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
