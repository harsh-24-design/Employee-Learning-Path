import React, { useState, useEffect } from 'react';
import { 
  LayoutDashboard, 
  User, 
  GitFork, 
  BookOpen, 
  TrendingUp, 
  Sparkles, 
  Database,
  GraduationCap,
  Users,
  Briefcase,
  Shield,
  UserPlus,
  LogIn,
  LogOut,
  CheckCircle2,
  X
} from 'lucide-react';
import { DashboardView } from './components/DashboardView';
import { ProfileView } from './components/ProfileView';
import { RoadmapView } from './components/RoadmapView';
import { CoursePageView } from './components/CoursePageView';
import { ProgressView } from './components/ProgressView';
import { AIAdvisorView } from './components/AIAdvisorView';
import { AdminCatalogView } from './components/AdminCatalogView';
import { ManagerTeamView } from './components/ManagerTeamView';
import { DashboardResponse, UserProfile, UserRole, api, tokenStorage } from './lib/api';

export function App() {
  const [activeTab, setActiveTab] = useState<
    'dashboard' | 'profile' | 'roadmap' | 'learning' | 'progress' | 'assistant' | 'catalog' | 'team'
  >('dashboard');
  
  // Current active user/employee context
  const [selectedEmpId, setSelectedEmpId] = useState<string>('LRN-PRIYA');
  const [currentUserRole, setCurrentUserRole] = useState<UserRole>('learner');
  const [currentUserName, setCurrentUserName] = useState<string>('Priya Sharma');
  const [currentUserEmail, setCurrentUserEmail] = useState<string>('priya@selflearner.io');
  const [isEmployee, setIsEmployee] = useState<boolean>(false);
  const [isAuthenticating, setIsAuthenticating] = useState<boolean>(true);

  const [dashboardData, setDashboardData] = useState<DashboardResponse | null>(null);
  const [loadingDashboard, setLoadingDashboard] = useState(true);
  const [selectedCourseForLearning, setSelectedCourseForLearning] = useState<string>('C101');

  // Auth modal state
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authMode, setAuthMode] = useState<'login' | 'register'>('register');
  const [regName, setRegName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regIsEmployee, setRegIsEmployee] = useState(false);
  const [regEmployeeId, setRegEmployeeId] = useState('');
  const [regDepartment, setRegDepartment] = useState('');
  const [regRole, setRegRole] = useState<UserRole>('learner');
  const [authError, setAuthError] = useState<string | null>(null);
  const [authSuccess, setAuthSuccess] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState(false);

  // Restore authenticated session from localStorage on startup
  useEffect(() => {
    initAuth();
  }, []);

  const initAuth = async () => {
    const token = tokenStorage.getToken();
    if (!token) {
      setIsAuthenticating(false);
      return;
    }
    try {
      const me = await api.getMe();
      if (me) {
        setSelectedEmpId(me.employee_id || me.user_id);
        setCurrentUserRole(me.role);
        setCurrentUserName(me.name);
        setCurrentUserEmail(me.email);
        setIsEmployee(me.is_employee);
      }
    } catch (e) {
      console.warn('Session restoration failed:', e);
      tokenStorage.clearToken();
    } finally {
      setIsAuthenticating(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, [selectedEmpId]);

  const loadDashboard = async () => {
    setLoadingDashboard(true);
    try {
      const data = await api.getDashboard(selectedEmpId);
      setDashboardData(data);
    } catch (e) {
      console.error('Failed to load dashboard:', e);
    } finally {
      setLoadingDashboard(false);
    }
  };

  const handleNavigate = (tab: string, context?: any) => {
    if (tab === 'learning' && context?.course_id) {
      setSelectedCourseForLearning(context.course_id);
    }
    setActiveTab(tab as any);
  };

  const handlePersonaSwitch = (empId: string, role: UserRole, name: string, email: string, isEmp: boolean) => {
    setSelectedEmpId(empId);
    setCurrentUserRole(role);
    setCurrentUserName(name);
    setCurrentUserEmail(email);
    setIsEmployee(isEmp);
    if (role === 'manager') {
      setActiveTab('team');
    } else if (activeTab === 'team') {
      setActiveTab('dashboard');
    }
  };

  const handleQuickDemoLogin = async (
    email: string,
    pass: string,
    fallbackEmpId: string,
    fallbackRole: UserRole,
    fallbackName: string,
    fallbackIsEmp: boolean
  ) => {
    try {
      const res = await api.login({ email, password: pass });
      const targetEmp = res.user.employee_id || res.user.user_id || fallbackEmpId;
      handlePersonaSwitch(targetEmp, res.user.role, res.user.name, res.user.email, res.user.is_employee);
    } catch (e) {
      console.warn('Quick login fell back to persona switch:', e);
      handlePersonaSwitch(fallbackEmpId, fallbackRole, fallbackName, email, fallbackIsEmp);
    }
  };

  const handleLogout = async () => {
    try {
      await api.logout();
    } catch (e) {
      console.warn('Logout request failed:', e);
    } finally {
      tokenStorage.clearToken();
      handlePersonaSwitch('LRN-PRIYA', 'learner', 'Priya Sharma', 'priya@selflearner.io', false);
      setActiveTab('dashboard');
    }
  };

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError(null);
    setAuthSuccess(null);
    setAuthLoading(true);

    try {
      if (authMode === 'register') {
        const res = await api.register({
          name: regName,
          email: regEmail,
          password: regPassword,
          role: regRole,
          is_employee: regIsEmployee,
          employee_id: regEmployeeId || undefined,
          department: regDepartment || (regIsEmployee ? 'Enterprise Engineering' : 'Independent Learning')
        });
        setAuthSuccess('Account created successfully! Logging you in...');
        setTimeout(() => {
          handlePersonaSwitch(
            res.user.employee_id || res.user.user_id,
            res.user.role,
            res.user.name,
            res.user.email,
            res.user.is_employee
          );
          setAuthModalOpen(false);
          setAuthSuccess(null);
        }, 1000);
      } else {
        const res = await api.login({
          email: regEmail,
          password: regPassword
        });
        setAuthSuccess('Login successful!');
        setTimeout(() => {
          handlePersonaSwitch(
            res.user.employee_id || res.user.user_id,
            res.user.role,
            res.user.name,
            res.user.email,
            res.user.is_employee
          );
          setAuthModalOpen(false);
          setAuthSuccess(null);
        }, 1000);
      }
    } catch (err: any) {
      setAuthError(err.message || 'Authentication failed');
    } finally {
      setAuthLoading(false);
    }
  };

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'profile', label: 'Profile & Goals', icon: User },
    { id: 'roadmap', label: 'Learning Roadmap', icon: GitFork },
    { id: 'learning', label: 'Course Workspace', icon: BookOpen },
    { id: 'progress', label: 'Skills & Progress', icon: TrendingUp },
    { id: 'assistant', label: 'AI Advisor', icon: Sparkles },
    { id: 'catalog', label: 'Multi-Platform Catalogue', icon: Database },
  ];

  if (currentUserRole === 'manager') {
    navItems.splice(1, 0, { id: 'team', label: 'Team Management', icon: Users });
  }

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900">
      {/* Top Global Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-600 via-teal-700 to-slate-800 text-white flex items-center justify-center shadow-sm shrink-0">
              <GraduationCap className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold text-slate-900 leading-tight">
                  Learning Path & Career Advisory Agent
                </h1>
                <span className="text-[10px] font-semibold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full border border-emerald-200">
                  Dual-Mode AI
                </span>
              </div>
              <p className="text-[11px] text-slate-500 hidden sm:block">
                Self-Directed Learning • Company-Assigned Tracks • Multi-Platform Discovery • Gemini Tutor
              </p>
            </div>
          </div>

          {/* Persona Switcher & Auth Trigger */}
          <div className="flex items-center gap-2 shrink-0">
            {/* Persona Quick Switcher */}
            {/* Persona Quick Switcher */}
            <div className="hidden md:flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs">
              <span className="text-[11px] font-semibold text-slate-500 px-2 flex items-center gap-1">
                <Users className="w-3.5 h-3.5" /> Demo Login:
              </span>
              <button
                onClick={() => handleQuickDemoLogin('learner@example.com', 'learner123', 'LRN-PRIYA', 'learner', 'Priya Sharma', false)}
                className={`px-2.5 py-1 rounded-lg font-medium transition ${
                  selectedEmpId === 'LRN-PRIYA' 
                    ? 'bg-white text-emerald-800 shadow-xs font-bold' 
                    : 'text-slate-600 hover:text-slate-900'
                }`}
                title="Independent Self-Learner (Priya Sharma)"
              >
                👩‍💻 Priya
              </button>
              <button
                onClick={() => handleQuickDemoLogin('employee@example.com', 'employee123', 'E2001', 'learner', 'Alex Mercer', true)}
                className={`px-2.5 py-1 rounded-lg font-medium transition ${
                  selectedEmpId === 'E2001' 
                    ? 'bg-white text-emerald-800 shadow-xs font-bold' 
                    : 'text-slate-600 hover:text-slate-900'
                }`}
                title="Company Employee (Alex Mercer)"
              >
                👨‍💻 Alex
              </button>
              <button
                onClick={() => handleQuickDemoLogin('manager@example.com', 'manager123', 'M1001', 'manager', 'David Chen', true)}
                className={`px-2.5 py-1 rounded-lg font-medium transition ${
                  selectedEmpId === 'M1001' 
                    ? 'bg-white text-blue-800 shadow-xs font-bold' 
                    : 'text-slate-600 hover:text-slate-900'
                }`}
                title="Engineering Manager (David Chen)"
              >
                👔 David
              </button>
              <button
                onClick={() => handleQuickDemoLogin('admin@example.com', 'admin123', 'A1001', 'admin', 'System Admin', true)}
                className={`px-2.5 py-1 rounded-lg font-medium transition ${
                  selectedEmpId === 'A1001' 
                    ? 'bg-white text-purple-800 shadow-xs font-bold' 
                    : 'text-slate-600 hover:text-slate-900'
                }`}
                title="Administrator"
              >
                🛡️ Admin
              </button>
            </div>

            {/* Active User Badge & Session Controls */}
            <div className="flex items-center gap-2">
              <div className="hidden lg:flex flex-col text-right">
                <span className="text-xs font-bold text-slate-800 leading-tight flex items-center justify-end gap-1.5">
                  {currentUserName}
                  <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-semibold ${
                    currentUserRole === 'admin' 
                      ? 'bg-purple-100 text-purple-800'
                      : currentUserRole === 'manager'
                        ? 'bg-blue-100 text-blue-800'
                        : 'bg-emerald-100 text-emerald-800'
                  }`}>
                    {currentUserRole}
                  </span>
                </span>
                <span className="text-[10px] text-slate-500">{currentUserEmail}</span>
              </div>

              {tokenStorage.getToken() ? (
                <button
                  onClick={handleLogout}
                  title="Sign Out"
                  className="flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-100 hover:bg-rose-50 hover:text-rose-700 text-slate-700 rounded-lg text-xs font-semibold border border-slate-200 transition"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Logout</span>
                </button>
              ) : (
                <button
                  onClick={() => {
                    setAuthMode('login');
                    setAuthModalOpen(true);
                  }}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold border border-slate-200 transition"
                >
                  <LogIn className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Sign In</span>
                </button>
              )}

              {/* Self-Register Button */}
              <button
                onClick={() => {
                  setAuthMode('register');
                  setAuthModalOpen(true);
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold transition shadow-xs"
              >
                <UserPlus className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Register</span>
              </button>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex space-x-1 overflow-x-auto scrollbar-none border-t border-slate-100">
          {navItems.map(item => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id as any)}
                className={`flex items-center gap-2 px-3.5 py-2.5 text-xs font-semibold whitespace-nowrap border-b-2 transition ${
                  isActive
                    ? 'border-emerald-600 text-emerald-700 bg-emerald-50/40'
                    : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-emerald-600' : 'text-slate-400'}`} />
                {item.label}
              </button>
            );
          })}
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeTab === 'dashboard' && (
          <DashboardView 
            data={dashboardData} 
            loading={loadingDashboard} 
            onNavigate={handleNavigate} 
          />
        )}

        {activeTab === 'team' && currentUserRole === 'manager' && (
          <ManagerTeamView />
        )}

        {activeTab === 'profile' && (
          <ProfileView 
            empId={selectedEmpId} 
            onProfileUpdated={loadDashboard} 
          />
        )}

        {activeTab === 'roadmap' && (
          <RoadmapView 
            empId={selectedEmpId} 
            onNavigateToCourse={(cId) => handleNavigate('learning', { course_id: cId })} 
          />
        )}

        {activeTab === 'learning' && (
          <CoursePageView 
            empId={selectedEmpId} 
            selectedCourseId={selectedCourseForLearning}
            onOpenChat={(cId) => handleNavigate('assistant', { course_id: cId })}
            onRefreshStats={loadDashboard}
          />
        )}

        {activeTab === 'progress' && (
          <ProgressView 
            empId={selectedEmpId} 
            onNavigateToCourse={(cId) => handleNavigate('learning', { course_id: cId })} 
          />
        )}

        {activeTab === 'assistant' && (
          <AIAdvisorView 
            empId={selectedEmpId} 
            initialCourseId={selectedCourseForLearning} 
          />
        )}

        {activeTab === 'catalog' && (
          <AdminCatalogView 
            isAdmin={currentUserRole === 'admin'} 
            onNavigateToCourse={(cId) => handleNavigate('learning', { course_id: cId })}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-500">
        <p>Personalized Learning & Career Development Agent • Next.js & FastAPI • Google Gemini API</p>
      </footer>

      {/* Auth / Self-Registration Modal */}
      {authModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <div className="flex justify-between items-center mb-4 pb-3 border-b border-slate-100">
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  {authMode === 'register' ? 'Create Your Account' : 'Account Login'}
                </h3>
                <p className="text-xs text-slate-500">
                  {authMode === 'register' 
                    ? 'Register independently without manager intervention' 
                    : 'Access your saved roadmaps and chat sessions'}
                </p>
              </div>
              <button 
                onClick={() => setAuthModalOpen(false)} 
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {authError && (
              <div className="mb-3 p-2.5 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-800">
                {authError}
              </div>
            )}
            {authSuccess && (
              <div className="mb-3 p-2.5 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                {authSuccess}
              </div>
            )}

            <form onSubmit={handleAuthSubmit} className="space-y-3.5">
              {authMode === 'register' && (
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Full Name</label>
                  <input
                    type="text"
                    required
                    value={regName}
                    onChange={e => setRegName(e.target.value)}
                    placeholder="e.g. Priya Sharma"
                    className="w-full text-xs p-2.5 bg-slate-50 border border-slate-300 rounded-lg outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Email Address</label>
                <input
                  type="email"
                  required
                  value={regEmail}
                  onChange={e => setRegEmail(e.target.value)}
                  placeholder="name@example.com"
                  className="w-full text-xs p-2.5 bg-slate-50 border border-slate-300 rounded-lg outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Password</label>
                <input
                  type="password"
                  required
                  minLength={6}
                  value={regPassword}
                  onChange={e => setRegPassword(e.target.value)}
                  placeholder="Minimum 6 characters"
                  className="w-full text-xs p-2.5 bg-slate-50 border border-slate-300 rounded-lg outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              {authMode === 'register' && (
                <>
                  <div className="pt-2 border-t border-slate-100">
                    <label className="flex items-center gap-2 cursor-pointer mb-2">
                      <input
                        type="checkbox"
                        checked={regIsEmployee}
                        onChange={e => setRegIsEmployee(e.target.checked)}
                        className="rounded text-emerald-600 focus:ring-emerald-500"
                      />
                      <span className="text-xs font-medium text-slate-700">
                        I am a company employee (optional corporate ID)
                      </span>
                    </label>
                  </div>

                  {regIsEmployee ? (
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">Employee ID</label>
                        <input
                          type="text"
                          value={regEmployeeId}
                          onChange={e => setRegEmployeeId(e.target.value)}
                          placeholder="e.g. E2004"
                          className="w-full text-xs p-2 bg-slate-50 border border-slate-300 rounded-lg outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">Department</label>
                        <input
                          type="text"
                          value={regDepartment}
                          onChange={e => setRegDepartment(e.target.value)}
                          placeholder="e.g. Engineering"
                          className="w-full text-xs p-2 bg-slate-50 border border-slate-300 rounded-lg outline-none"
                        />
                      </div>
                    </div>
                  ) : (
                    <div className="p-2.5 bg-emerald-50/60 border border-emerald-100 rounded-lg text-[11px] text-emerald-800">
                      ✨ <strong>Independent Learner Mode:</strong> No company employee ID required! You can save your goals, customize skills, and track personal progress freely.
                    </div>
                  )}

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Account Role</label>
                    <select
                      value={regRole}
                      onChange={e => setRegRole(e.target.value as any)}
                      className="w-full text-xs p-2 bg-slate-50 border border-slate-300 rounded-lg outline-none"
                    >
                      <option value="learner">Individual Learner / Employee</option>
                      <option value="manager">Manager (Can assign company goals)</option>
                    </select>
                    <p className="text-[10px] text-slate-400 mt-1">
                      Note: System Administrator privileges require system configuration and cannot be self-assigned.
                    </p>
                  </div>
                </>
              )}

              <div className="pt-3">
                <button
                  type="submit"
                  disabled={authLoading}
                  className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition shadow-sm"
                >
                  {authLoading 
                    ? 'Processing...' 
                    : authMode === 'register' 
                      ? 'Register Account' 
                      : 'Log In'}
                </button>
              </div>
            </form>

            <div className="mt-4 pt-3 border-t border-slate-100 text-center text-xs text-slate-500">
              {authMode === 'register' ? (
                <span>
                  Already have an account?{' '}
                  <button 
                    onClick={() => {
                      setAuthMode('login');
                      setAuthError(null);
                    }} 
                    className="text-emerald-700 font-semibold hover:underline"
                  >
                    Log In
                  </button>
                </span>
              ) : (
                <span>
                  Need an independent account?{' '}
                  <button 
                    onClick={() => {
                      setAuthMode('register');
                      setAuthError(null);
                    }} 
                    className="text-emerald-700 font-semibold hover:underline"
                  >
                    Register here
                  </button>
                </span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
