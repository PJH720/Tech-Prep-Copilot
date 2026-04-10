import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { ResumeData, JDData, GapAnalysis, InterviewMessage, CompanyInfo } from '../types';

interface AppState {
  resume: ResumeData | null;
  jd: JDData | null;
  analysis: GapAnalysis | null;
  interviewHistory: InterviewMessage[];
  selectedCompany: CompanyInfo | null;
  isLoading: boolean;
  
  setResume: (resume: ResumeData | null) => void;
  setJD: (jd: JDData | null) => void;
  setAnalysis: (analysis: GapAnalysis | null) => void;
  addInterviewMessage: (message: InterviewMessage) => void;
  setInterviewHistory: (history: InterviewMessage[]) => void;
  setSelectedCompany: (company: CompanyInfo | null) => void;
  setIsLoading: (loading: boolean) => void;
  resetAll: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      resume: null,
      jd: null,
      analysis: null,
      interviewHistory: [],
      selectedCompany: null,
      isLoading: false,

      setResume: (resume) => set({ resume }),
      setJD: (jd) => set({ jd }),
      setAnalysis: (analysis) => set({ analysis }),
      addInterviewMessage: (message) => set((state) => ({ 
        interviewHistory: [...state.interviewHistory, message] 
      })),
      setInterviewHistory: (history) => set({ interviewHistory: history }),
      setSelectedCompany: (company) => set({ selectedCompany: company }),
      setIsLoading: (loading) => set({ isLoading: loading }),
      resetAll: () => set({ 
        resume: null, 
        jd: null, 
        analysis: null, 
        interviewHistory: [], 
        selectedCompany: null 
      }),
    }),
    {
      name: 'tech-prep-storage',
    }
  )
);
