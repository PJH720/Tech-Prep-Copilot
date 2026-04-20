import { create } from 'zustand';
import { ResumeData, JDData, GapAnalysis, InterviewMessage, CompanyInfo, SourceItem } from '../types';

export interface BackendHealth {
  status: string;
  rag_ready: boolean;
  chunk_count: number;
  tavily_ready: boolean;
  llm_provider_order: string;
  llm_gemini_configured: boolean;
  llm_openai_configured: boolean;
  llm_upstage_configured: boolean;
}

interface AppState {
  resume: ResumeData | null;
  jd: JDData | null;
  analysis: GapAnalysis | null;
  analysisSources: SourceItem[];
  analysisError: string | null;
  backendHealth: BackendHealth | null;
  interviewHistory: InterviewMessage[];
  selectedCompany: CompanyInfo | null;
  isAnalyzing: boolean;
  isInterviewing: boolean;

  setResume: (resume: ResumeData | null) => void;
  setJD: (jd: JDData | null) => void;
  setAnalysis: (analysis: GapAnalysis | null) => void;
  setAnalysisSources: (sources: SourceItem[]) => void;
  setAnalysisError: (error: string | null) => void;
  setBackendHealth: (health: BackendHealth | null) => void;
  addInterviewMessage: (message: InterviewMessage) => void;
  setInterviewHistory: (history: InterviewMessage[]) => void;
  setSelectedCompany: (company: CompanyInfo | null) => void;
  setIsAnalyzing: (loading: boolean) => void;
  setIsInterviewing: (loading: boolean) => void;
  resetAll: () => void;
}

export const useAppStore = create<AppState>()((set) => ({
  resume: null,
  jd: null,
  analysis: null,
  analysisSources: [],
  analysisError: null,
  backendHealth: null,
  interviewHistory: [],
  selectedCompany: null,
  isAnalyzing: false,
  isInterviewing: false,

  setResume: (resume) => set({ resume }),
  setJD: (jd) => set({ jd }),
  setAnalysis: (analysis) => set({ analysis }),
  setAnalysisSources: (sources) => set({ analysisSources: sources }),
  setAnalysisError: (analysisError) => set({ analysisError }),
  setBackendHealth: (backendHealth) => set({ backendHealth }),
  addInterviewMessage: (message) => set((state) => ({
    interviewHistory: [...state.interviewHistory, message]
  })),
  setInterviewHistory: (history) => set({ interviewHistory: history }),
  setSelectedCompany: (company) => set({ selectedCompany: company }),
  setIsAnalyzing: (loading) => set({ isAnalyzing: loading }),
  setIsInterviewing: (loading) => set({ isInterviewing: loading }),
  resetAll: () => set({
    resume: null,
    jd: null,
    analysis: null,
    analysisSources: [],
    analysisError: null,
    interviewHistory: [],
    selectedCompany: null,
    isAnalyzing: false,
    isInterviewing: false,
  }),
}));
