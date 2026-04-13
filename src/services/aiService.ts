import OpenAI from "openai";
import { ResumeData, JDData, GapAnalysis, InterviewMessage, CompanyInfo, RagInsights, SourceItem, AgentBrief } from "../types";

const ai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY || "",
  dangerouslyAllowBrowser: true,
});
const OPENAI_MODEL = "gpt-4o-mini";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

/**
 * Fetch relevant RAG context from the FastAPI backend.
 * Returns a formatted string of the top matching blog excerpts,
 * or null if the backend is unavailable (graceful degradation).
 */
export const fetchRagInsights = async (
  companyId: string,
  query: string,
  topK = 3
): Promise<RagInsights> => {
  try {
    const res = await fetch(`${BACKEND_URL}/api/rag/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ company_id: companyId, query, top_k: topK }),
    });
    if (!res.ok) {
      return { contextText: "", sources: [], ragAvailable: false };
    }
    const data: {
      results: Array<{ content: string; title: string; source: string; score: number }>;
      rag_available: boolean;
    } = await res.json();
    const sources: SourceItem[] = (data.results || []).map((item) => ({
      content: item.content,
      title: item.title,
      source: item.source,
      score: item.score,
    }));
    const contextText = sources
      .map((source, i) => `[${i + 1}] ${source.title}\n${source.content}`)
      .join("\n\n---\n\n");
    return { contextText, sources, ragAvailable: Boolean(data.rag_available) };
  } catch {
    // Backend not running — degrade gracefully to prompt-only mode
    return { contextText: "", sources: [], ragAvailable: false };
  }
};

export const getAgentBrief = async (
  companyId: string,
  query: string,
  topK = 3,
  maxResults = 5
): Promise<AgentBrief | null> => {
  try {
    const res = await fetch(`${BACKEND_URL}/api/agent/brief`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        company_id: companyId,
        query,
        top_k: topK,
        max_results: maxResults,
      }),
    });
    if (!res.ok) return null;
    const data: {
      summary: string;
      rag_results: Array<{ content: string; title: string; source: string; score: number }>;
      realtime_results: Array<{ content: string; title: string; source: string; score: number }>;
      used_realtime_search: boolean;
      rag_available: boolean;
    } = await res.json();
    return {
      summary: data.summary,
      ragResults: data.rag_results || [],
      realtimeResults: data.realtime_results || [],
      usedRealtimeSearch: data.used_realtime_search,
      ragAvailable: data.rag_available,
    };
  } catch {
    return null;
  }
};

export const analyzeGap = async (
  resume: ResumeData,
  jd: JDData,
  company?: CompanyInfo
): Promise<{ analysis: GapAnalysis; sources: SourceItem[]; ragAvailable: boolean }> => {
  const rag = company
    ? await fetchRagInsights(
        company.id,
        `${company.name} engineering requirements ${jd.text.slice(0, 500)}`
      )
    : { contextText: "", sources: [], ragAvailable: false };
  const ragSection = rag.contextText
    ? `
    Retrieved Engineering Context:
    ${rag.contextText}
    `
    : "";

  const prompt = `
    You are a 10-year experienced IT recruitment consultant.
    Compare the following Resume and Job Description (JD).
    Analyze the strengths, weaknesses, and provide recommendations for the candidate.
    Also, provide a match score from 0 to 100.
    ${ragSection}

    Resume:
    ${resume.text}

    Job Description:
    ${jd.text}

    Return ONLY valid JSON in this exact shape:
    {
      "strengths": string[],
      "weaknesses": string[],
      "recommendations": string[],
      "matchScore": number
    }
  `;

  const response = await ai.chat.completions.create({
    model: OPENAI_MODEL,
    messages: [
      {
        role: "system",
        content: "You are a senior IT recruitment consultant. Always return only valid JSON.",
      },
      { role: "user", content: prompt },
    ],
    response_format: { type: "json_object" },
  });

  const responseText = response.choices[0]?.message?.content;
  if (!responseText) throw new Error("Empty response from OpenAI (analyzeGap)");
  return {
    analysis: JSON.parse(responseText),
    sources: rag.sources,
    ragAvailable: rag.ragAvailable,
  };
};

export const generateInterviewQuestion = async (
  resume: ResumeData,
  company: CompanyInfo,
  history: InterviewMessage[],
  contextSummary?: string,
  recentAssistantQuestions: string[] = []
): Promise<string> => {
  const historyText = history.map(m => `${m.role}: ${m.content}`).join("\n");
  
  const ragSection = contextSummary
    ? `\n\nEngineering Context:\n${contextSummary}\n\nUse the context above to ask a grounded and specific question.`
    : "";
  const antiRepeatSection = recentAssistantQuestions.length
    ? `\n\nDo not repeat these previous interviewer questions:\n${recentAssistantQuestions.join("\n")}`
    : "";

  const prompt = `
    You are a senior engineer interviewer at ${company.name}.
    Company Tech Stack: ${company.recentTechStack.join(", ")}
    Company Description: ${company.description}
    ${ragSection}
    ${antiRepeatSection}

    Candidate Resume:
    ${resume.text}

    Interview History:
    ${historyText}

    Based on the candidate's resume and the company's technical interests, ask a deep technical follow-up question.
    Focus on one of their projects and how it relates to the company's tech stack.
    Be professional and challenging.
    Return ONLY valid JSON in this exact shape:
    { "question": string }
  `;

  const response = await ai.chat.completions.create({
    model: OPENAI_MODEL,
    messages: [
      {
        role: "system",
        content: "You are a senior engineering interviewer. Always return only valid JSON.",
      },
      { role: "user", content: prompt },
    ],
    response_format: { type: "json_object" },
  });

  const responseText = response.choices[0]?.message?.content;
  if (!responseText) {
    return "Could you tell me more about your most significant project?";
  }

  try {
    const parsed: { question?: string } = JSON.parse(responseText);
    return parsed.question?.trim() || "Could you tell me more about your most significant project?";
  } catch {
    return "Could you tell me more about your most significant project?";
  }
};

export const evaluateAnswer = async (
  question: string,
  answer: string,
  company: CompanyInfo,
  contextSummary?: string
): Promise<InterviewMessage['feedback']> => {
  const ragSection = contextSummary
    ? `\n\nEngineering Context for grading:\n${contextSummary}`
    : "";

  const prompt = `
    You are a senior engineer interviewer at ${company.name}.
    Evaluate the candidate's answer to your question.
    ${ragSection}

    Question: ${question}
    Answer: ${answer}

    Provide feedback on technical accuracy (0-100), logic (0-100), and a suggestion for improvement.
    If possible, include a reference quote or concept from the company's actual engineering blog or tech stack: ${company.recentTechStack.join(", ")}.

    Return ONLY valid JSON in this exact shape:
    {
      "accuracy": number,
      "logic": number,
      "suggestion": string,
      "referenceQuote": string
    }
  `;

  const response = await ai.chat.completions.create({
    model: OPENAI_MODEL,
    messages: [
      {
        role: "system",
        content: "You are a senior engineering interviewer. Always return only valid JSON.",
      },
      { role: "user", content: prompt },
    ],
    response_format: { type: "json_object" },
  });

  const responseText = response.choices[0]?.message?.content;
  if (!responseText) throw new Error("Empty response from OpenAI (evaluateAnswer)");
  return JSON.parse(responseText);
};
