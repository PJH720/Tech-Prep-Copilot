import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface AnalysisResult {
  strengths: string[];
  gaps: string[];
  suggestions: string[];
  overallScore?: number;
}

export interface InterviewEntry {
  question: string;
  answer: string;
  feedback?: string;
}

interface AppState {
  // State
  resumeText: string;
  jdText: string;
  analysisResult: AnalysisResult | null;
  interviewHistory: InterviewEntry[];

  // Actions
  setResumeText: (text: string) => void;
  setJdText: (text: string) => void;
  setAnalysisResult: (result: AnalysisResult | null) => void;
  addInterviewEntry: (entry: InterviewEntry) => void;
  resetInterviewHistory: () => void;
  resetAll: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      // Initial state
      resumeText: "",
      jdText: "",
      analysisResult: null,
      interviewHistory: [],

      // Actions
      setResumeText: (text) => set({ resumeText: text }),
      setJdText: (text) => set({ jdText: text }),
      setAnalysisResult: (result) => set({ analysisResult: result }),
      addInterviewEntry: (entry) =>
        set((state) => ({
          interviewHistory: [...state.interviewHistory, entry],
        })),
      resetInterviewHistory: () => set({ interviewHistory: [] }),
      resetAll: () =>
        set({
          resumeText: "",
          jdText: "",
          analysisResult: null,
          interviewHistory: [],
        }),
    }),
    {
      name: "app-storage",
      // resumeText, jdText만 localStorage에 persist
      partialize: (state) => ({
        resumeText: state.resumeText,
        jdText: state.jdText,
      }),
    }
  )
);
