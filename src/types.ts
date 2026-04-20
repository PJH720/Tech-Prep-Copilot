export interface ResumeData {
  text: string;
  name?: string;
  parsedAt: string;
}

export interface JDData {
  text: string;
  companyName?: string;
  role?: string;
}

export interface GapAnalysis {
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
  matchScore: number;
}

export interface SourceItem {
  title: string;
  source: string;
  content: string;
  score?: number;
}

export interface RagInsights {
  contextText: string;
  sources: SourceItem[];
  ragAvailable: boolean;
}

export interface AgentBrief {
  summary: string;
  ragResults: SourceItem[];
  realtimeResults: SourceItem[];
  usedRealtimeSearch: boolean;
  ragAvailable: boolean;
}

export interface InterviewMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  asked_by?: 'interviewer' | 'feedback_giver'; // 질문한 캐릭터
  feedback?: {
    accuracy: number;
    logic: number;
    suggestion: string;
    referenceQuote?: string;
  };
}

export interface CompanyInfo {
  id: string;
  name: string;
  logo: string;
  description: string;
  techBlogUrl: string;
  recentTechStack: string[];
}
