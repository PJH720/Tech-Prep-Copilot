import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { ResumeData, JDData, GapAnalysis, InterviewMessage, CompanyInfo, SourceItem } from '../types';

interface AppState {
  resume: ResumeData | null;
  jd: JDData | null;
  analysis: GapAnalysis | null;
  analysisSources: SourceItem[];
  interviewHistory: InterviewMessage[];
  selectedCompany: CompanyInfo | null;
  isAnalyzing: boolean;
  isInterviewing: boolean;

  setResume: (resume: ResumeData | null) => void;
  setJD: (jd: JDData | null) => void;
  setAnalysis: (analysis: GapAnalysis | null) => void;
  setAnalysisSources: (sources: SourceItem[]) => void;
  addInterviewMessage: (message: InterviewMessage) => void;
  setInterviewHistory: (history: InterviewMessage[]) => void;
  setSelectedCompany: (company: CompanyInfo | null) => void;
  setIsAnalyzing: (loading: boolean) => void;
  setIsInterviewing: (loading: boolean) => void;
  resetAll: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      resume: null,
      jd: null,
      analysis: null,
      analysisSources: [],
      interviewHistory: [],
      selectedCompany: null,
      isAnalyzing: false,
      isInterviewing: false,

      setResume: (resume) => set({ resume }),
      setJD: (jd) => set({ jd }),
      setAnalysis: (analysis) => set({ analysis }),
      setAnalysisSources: (sources) => set({ analysisSources: sources }),
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
        interviewHistory: [],
        selectedCompany: null
      }),
    }),
    {
      name: 'tech-prep-storage',
    }
  )
);
