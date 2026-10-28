import React, { useState, useEffect, useRef } from 'react';
import { 
  Sparkles, 
  Send, 
  Bot, 
  User, 
  BookOpen, 
  FileText, 
  ShieldAlert, 
  Lightbulb,
  MessageSquare,
  PlusCircle,
  Clock,
  Layers,
  HelpCircle
} from 'lucide-react';
import { Course, ChatMessage, ChatConversation, PlanMode, api } from '../lib/api';

interface AIAdvisorViewProps {
  empId: string;
  initialCourseId?: string;
}

export const AIAdvisorView: React.FC<AIAdvisorViewProps> = ({ empId, initialCourseId }) => {
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState<string>(initialCourseId || '');
  const [planMode, setPlanMode] = useState<PlanMode>('self_directed');
  
  // Conversations list & active conversation
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string>('');
  
  const [messages, setMessages] = useState<Array<{
    sender: 'user' | 'assistant';
    text: string;
    citations?: any[];
    course_id?: string;
  }>>([]);
  const [inputValue, setInputValue] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadInitialData();
  }, [empId]);

  useEffect(() => {
    if (initialCourseId) {
      setSelectedCourseId(initialCourseId);
    }
  }, [initialCourseId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadInitialData = async () => {
    try {
      const [allCourses, convs] = await Promise.all([
        api.getCourses(),
        api.getChatConversations(empId)
      ]);
      setCourses(allCourses);
      setConversations(convs);

      const initialId = `CONV-${Date.now()}`;
      setActiveConvId(initialId);
      setMessages([
        {
          sender: 'assistant',
          text: `Hello! I am your AI Learning Path Advisor. I support both self-directed personal development and company-assigned tracks. How can I help you master your concepts or roadmap today?`,
          citations: []
        }
      ]);
    } catch (e) {
      console.error('Failed to load chat data:', e);
    }
  };

  const handleStartNewConversation = async () => {
    try {
      const newConv = await api.createChatConversation(empId, selectedCourseId || undefined);
      setActiveConvId(newConv.conversation_id);
      setConversations(prev => [newConv, ...prev]);
      setMessages([
        {
          sender: 'assistant',
          text: `Started new doubt resolution session. Ask me about course concepts, coding exercises, or roadmap pacing!`,
          citations: []
        }
      ]);
    } catch (e) {
      const fallbackId = `CONV-${Date.now()}`;
      setActiveConvId(fallbackId);
    }
  };

  const handleSelectConversation = async (convId: string) => {
    setActiveConvId(convId);
    try {
      const history = await api.getChatHistory(convId);
      if (history.length > 0) {
        setMessages(history.map(m => ({
          sender: m.sender,
          text: m.message,
          citations: m.citations,
          course_id: m.course_id
        })));
      }
    } catch (e) {
      console.error('Failed to load conversation history:', e);
    }
  };

  const handleSend = async (textToSend?: string) => {
    const text = textToSend || inputValue;
    if (!text.trim() || sending) return;

    const userMsg = {
      sender: 'user' as const,
      text: text,
      course_id: selectedCourseId || undefined
    };

    setMessages(prev => [...prev, userMsg]);
    if (!textToSend) setInputValue('');
    setSending(true);

    try {
      const response = await api.sendChatMessage(
        empId,
        text,
        selectedCourseId || undefined,
        activeConvId,
        planMode
      );

      setMessages(prev => [
        ...prev,
        {
          sender: 'assistant' as const,
          text: response.reply,
          citations: response.citations || [],
          course_id: response.course_id
        }
      ]);
    } catch (e) {
      setMessages(prev => [
        ...prev,
        {
          sender: 'assistant' as const,
          text: 'Notice: Advisory service connection error. Please verify backend service status.',
          citations: []
        }
      ]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 pb-3 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-bold text-emerald-800 bg-emerald-100 px-2.5 py-0.5 rounded-full flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5" /> AI Learning Assistant
            </span>
            <span className="text-xs text-slate-500">Google Gemini API • Course-Aware RAG</span>
          </div>
          <h2 className="text-xl font-bold text-slate-900">Personalized Doubt Resolution & Guidance</h2>
        </div>

        {/* Dual Mode Switcher */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-slate-500">Context:</span>
          <select
            value={planMode}
            onChange={e => setPlanMode(e.target.value as PlanMode)}
            className="text-xs font-bold px-3 py-1.5 bg-white border border-slate-300 rounded-lg outline-none"
          >
            <option value="self_directed">🎯 Self-Directed Learning</option>
            <option value="company_assigned">🏢 Company-Assigned Track</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Sidebar: Past Conversations & Course Context */}
        <div className="lg:col-span-1 space-y-4">
          <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-xs font-bold text-slate-700">Chat History</span>
              <button
                onClick={handleStartNewConversation}
                className="text-emerald-700 hover:text-emerald-800 text-xs font-semibold flex items-center gap-1"
              >
                <PlusCircle className="w-3.5 h-3.5" /> New Chat
              </button>
            </div>

            <div className="space-y-1.5 max-h-[160px] overflow-y-auto">
              {conversations.length === 0 ? (
                <p className="text-[11px] text-slate-400 py-2">No past conversations recorded.</p>
              ) : (
                conversations.map(conv => (
                  <button
                    key={conv.conversation_id}
                    onClick={() => handleSelectConversation(conv.conversation_id)}
                    className={`w-full text-left p-2 rounded-lg text-xs truncate transition flex items-center gap-2 ${
                      activeConvId === conv.conversation_id 
                        ? 'bg-emerald-50 text-emerald-900 font-bold border border-emerald-200' 
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    <MessageSquare className="w-3.5 h-3.5 shrink-0 text-slate-400" />
                    <span className="truncate">{conv.title || conv.conversation_id}</span>
                  </button>
                ))
              )}
            </div>
          </div>

          <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs space-y-3">
            <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
              <BookOpen className="w-3.5 h-3.5 text-blue-600" /> Grounding Course Context
            </span>
            <select
              value={selectedCourseId}
              onChange={e => setSelectedCourseId(e.target.value)}
              className="w-full text-xs p-2 bg-slate-50 border border-slate-300 rounded-lg outline-none"
            >
              <option value="">General Learning Question</option>
              {courses.map(c => (
                <option key={c.course_id} value={c.course_id}>
                  {c.course_id}: {c.title} ({c.platform})
                </option>
              ))}
            </select>
            <p className="text-[11px] text-slate-400">
              The AI dynamically grounds its answers in this course's syllabus and difficulty level.
            </p>
          </div>
        </div>

        {/* Chat Main Area */}
        <div className="lg:col-span-3 bg-white rounded-2xl border border-slate-200/80 shadow-xs flex flex-col h-[580px]">
          {/* Quick Prompts Bar */}
          <div className="p-3 bg-slate-50 border-b border-slate-200 flex flex-wrap gap-2 text-xs">
            <button
              onClick={() => handleSend("Can you explain the main concept of this course at my current proficiency level?")}
              className="px-2.5 py-1 bg-white border border-slate-200 rounded-md text-slate-700 hover:border-emerald-500 hover:text-emerald-700 transition"
            >
              💡 Explain at my proficiency level
            </button>
            <button
              onClick={() => handleSend("Can you give me a step-by-step hint for the practical exercises?")}
              className="px-2.5 py-1 bg-white border border-slate-200 rounded-md text-slate-700 hover:border-emerald-500 hover:text-emerald-700 transition"
            >
              🧩 Give me a hint for exercises
            </button>
            <button
              onClick={() => handleSend("What are the official certificate requirements and credential types for this course?")}
              className="px-2.5 py-1 bg-white border border-slate-200 rounded-md text-slate-700 hover:border-emerald-500 hover:text-emerald-700 transition"
            >
              🎓 Explain certificate options
            </button>
            <button
              onClick={() => handleSend("What is the company learning policy regarding budgets and weekly study hours?")}
              className="px-2.5 py-1 bg-white border border-slate-200 rounded-md text-slate-700 hover:border-emerald-500 hover:text-emerald-700 transition"
            >
              📜 Corporate policy inquiry
            </button>
          </div>

          {/* Messages Feed */}
          <div className="flex-1 p-4 overflow-y-auto space-y-4">
            {messages.map((m, idx) => (
              <div 
                key={idx}
                className={`flex gap-3 ${m.sender === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {m.sender === 'assistant' && (
                  <div className="w-8 h-8 rounded-full bg-emerald-600 text-white flex items-center justify-center shrink-0 shadow-xs">
                    <Bot className="w-4 h-4" />
                  </div>
                )}

                <div className={`max-w-[80%] rounded-2xl p-4 text-xs leading-relaxed ${
                  m.sender === 'user' 
                    ? 'bg-emerald-600 text-white rounded-br-none' 
                    : 'bg-slate-100 text-slate-800 rounded-bl-none border border-slate-200/60'
                }`}>
                  <p className="whitespace-pre-wrap">{m.text}</p>

                  {/* Citations */}
                  {m.citations && m.citations.length > 0 && (
                    <div className="mt-3 pt-2 border-t border-slate-200/60 text-[10px] space-y-1 text-slate-600">
                      <span className="font-bold flex items-center gap-1">
                        <FileText className="w-3 h-3 text-emerald-600" /> Policy Evidence Citations:
                      </span>
                      {m.citations.map((c, i) => (
                        <div key={i} className="bg-white/80 p-1.5 rounded border border-slate-200">
                          <strong>{c.document}</strong> • {c.section} (relevance: {c.score})
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {m.sender === 'user' && (
                  <div className="w-8 h-8 rounded-full bg-slate-800 text-white flex items-center justify-center shrink-0">
                    <User className="w-4 h-4" />
                  </div>
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Box */}
          <div className="p-3 border-t border-slate-200 flex items-center gap-2">
            <input
              type="text"
              placeholder="Ask a doubt, request hints, or ask about roadmap pacing..."
              value={inputValue}
              onChange={e => setInputValue(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSend()}
              className="flex-1 text-xs px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl outline-none focus:ring-2 focus:ring-emerald-500"
            />
            <button
              onClick={() => handleSend()}
              disabled={sending || !inputValue.trim()}
              className="p-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white rounded-xl transition shadow-xs"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
