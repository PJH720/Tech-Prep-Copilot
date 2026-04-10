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

export interface InterviewMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
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
