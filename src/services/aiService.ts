import OpenAI from "openai";
import { ResumeData, JDData, GapAnalysis, InterviewMessage, CompanyInfo, RagInsights, SourceItem, AgentBrief } from "../types";

const ai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY || "",
  dangerouslyAllowBrowser: true,
});
const OPENAI_MODEL = "gpt-4o-mini";
const DEFAULT_INTERVIEW_QUESTION = "Could you tell me more about your most significant project?";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
const BACKEND_TIMEOUT_MS = 4500;
const COMPANY_KEYWORDS: Record<string, string[]> = {
  toss: ["toss", "toss.tech", "toss.im"],
  kakao: ["kakao", "tech.kakao.com"],
  naver: ["naver", "d2.naver.com"],
  coupang: ["coupang", "medium.com"],
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const isStringArray = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every((item) => typeof item === "string");

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value);

const assertNonEmptyContent = (
  content: string | null | undefined,
  context: string
): string => {
  if (typeof content !== "string" || content.trim().length === 0) {
    throw new Error(`Received empty or invalid response from the LLM (${context}).`);
  }
  return content;
};

const parseJsonOrThrow = <T>(content: string, context: string): T => {
  try {
    return JSON.parse(content) as T;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(`Failed to parse LLM JSON response (${context}): ${message}`);
  }
};

const isGapAnalysis = (value: unknown): value is GapAnalysis => {
  if (!isRecord(value)) return false;
  return (
    isStringArray(value.strengths) &&
    isStringArray(value.weaknesses) &&
    isStringArray(value.recommendations) &&
    isFiniteNumber(value.matchScore)
  );
};

const isInterviewQuestionPayload = (value: unknown): value is { question: string } => {
  if (!isRecord(value)) return false;
  return typeof value.question === "string" && value.question.trim().length > 0;
};

const isInterviewFeedback = (value: unknown): value is InterviewMessage["feedback"] => {
  if (!isRecord(value)) return false;
  const hasReferenceQuote =
    value.referenceQuote === undefined || typeof value.referenceQuote === "string";
  return (
    isFiniteNumber(value.accuracy) &&
    isFiniteNumber(value.logic) &&
    typeof value.suggestion === "string" &&
    hasReferenceQuote
  );
};

const normalizeCompanyId = (domainOrCompany = ""): string => {
  const normalized = domainOrCompany.trim().toLowerCase();
  if (!normalized) return "";
  if (COMPANY_KEYWORDS[normalized]) return normalized;

  const matchedEntry = Object.entries(COMPANY_KEYWORDS).find(([, keywords]) =>
    keywords.some((keyword) => normalized.includes(keyword))
  );
  return matchedEntry?.[0] ?? "";
};

const fetchJsonWithTimeout = async <T>(
  path: string,
  payload: Record<string, unknown>,
  timeoutMs = BACKEND_TIMEOUT_MS
): Promise<T | null> => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${BACKEND_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  } finally {
    clearTimeout(timeoutId);
  }
};

/**
 * Fetch relevant RAG context from the FastAPI backend.
 * Returns a formatted string of the top matching blog excerpts,
 * or null if the backend is unavailable (graceful degradation).
 */
export const fetchRagInsights = async (
  query: string,
  domainOrCompany = "",
  topK = 3
): Promise<RagInsights> => {
  const companyId = normalizeCompanyId(domainOrCompany);
  const data = await fetchJsonWithTimeout<{
    results: Array<{ content: string; title: string; source: string; score: number }>;
    rag_available: boolean;
  }>("/api/rag/search", { company_id: companyId, query, top_k: topK });

  if (!data) {
    return { contextText: "", sources: [], ragAvailable: false };
  }

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
};

export const getAgentBrief = async (
  query: string,
  domainOrCompany = "",
  topK = 3,
  maxResults = 5
): Promise<AgentBrief | null> => {
  const companyId = normalizeCompanyId(domainOrCompany);
  const data = await fetchJsonWithTimeout<{
    summary: string;
    rag_results: Array<{ content: string; title: string; source: string; score: number }>;
    realtime_results: Array<{ content: string; title: string; source: string; score: number }>;
    used_realtime_search: boolean;
    rag_available: boolean;
  }>("/api/agent/brief", {
    company_id: companyId,
    query,
    top_k: topK,
    max_results: maxResults,
  });

  if (!data) return null;

  return {
    summary: data.summary,
    ragResults: data.rag_results || [],
    realtimeResults: data.realtime_results || [],
    usedRealtimeSearch: data.used_realtime_search,
    ragAvailable: data.rag_available,
  }
};

export const analyzeGap = async (
  resume: ResumeData,
  jd: JDData,
  company?: CompanyInfo
): Promise<{ analysis: GapAnalysis; sources: SourceItem[]; ragAvailable: boolean }> => {
  const rag = company
    ? await fetchRagInsights(
        `${company.name} engineering requirements ${jd.text.slice(0, 500)}`,
        company.id
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
        content:
          "You are a senior IT recruitment consultant. Ground your analysis in the provided Retrieved Engineering Context when available, and avoid inventing unsupported company details. Always return only valid JSON.",
      },
      { role: "user", content: prompt },
    ],
    response_format: { type: "json_object" },
  });

  const responseText = assertNonEmptyContent(
    response.choices[0]?.message?.content,
    "analyzeGap"
  );
  const parsed = parseJsonOrThrow<unknown>(responseText, "analyzeGap");
  if (!isGapAnalysis(parsed)) {
    throw new Error("Invalid response schema from the LLM (analyzeGap).");
  }

  return {
    analysis: parsed,
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
  const resolvedContextSummary =
    contextSummary ||
    (
      await getAgentBrief(
        `${company.name} interview question grounded in resume context ${(historyText || resume.text).slice(0, 700)}`,
        company.id
      )
    )?.summary;
  
  const ragSection = resolvedContextSummary
    ? `\n\nEngineering Context:\n${resolvedContextSummary}\n\nUse the context above as the primary grounding for your question. If context is missing for a claim, avoid fabricating details.`
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
        content:
          "You are a senior engineering interviewer. When Engineering Context is provided, ground your question in it and avoid unsupported assumptions. Always return only valid JSON.",
      },
      { role: "user", content: prompt },
    ],
    response_format: { type: "json_object" },
  });

  try {
    const responseText = assertNonEmptyContent(
      response.choices[0]?.message?.content,
      "generateInterviewQuestion"
    );
    const parsed = parseJsonOrThrow<unknown>(responseText, "generateInterviewQuestion");
    if (!isInterviewQuestionPayload(parsed)) {
      throw new Error("Invalid response schema from the LLM (generateInterviewQuestion).");
    }
    return parsed.question.trim() || DEFAULT_INTERVIEW_QUESTION;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`Failed to build interview question from LLM response: ${message}`);
    return DEFAULT_INTERVIEW_QUESTION;
  }
};

export const evaluateAnswer = async (
  question: string,
  answer: string,
  company: CompanyInfo,
  contextSummary?: string
): Promise<InterviewMessage['feedback']> => {
  const resolvedContextSummary =
    contextSummary ||
    (
      await getAgentBrief(
        `${company.name} evaluate interview answer context. Question: ${question}. Answer: ${answer}`.slice(0, 900),
        company.id
      )
    )?.summary;

  const ragSection = resolvedContextSummary
    ? `\n\nEngineering Context for grading:\n${resolvedContextSummary}\n\nUse this context as the primary evidence when scoring and feedback.`
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
        content:
          "You are a senior engineering interviewer. Ground evaluation in provided Engineering Context when available and do not fabricate references. Always return only valid JSON.",
      },
      { role: "user", content: prompt },
    ],
    response_format: { type: "json_object" },
  });

  const responseText = assertNonEmptyContent(
    response.choices[0]?.message?.content,
    "evaluateAnswer"
  );
  const parsed = parseJsonOrThrow<unknown>(responseText, "evaluateAnswer");
  if (!isInterviewFeedback(parsed)) {
    throw new Error("Invalid response schema from the LLM (evaluateAnswer).");
  }
  return parsed;
};
