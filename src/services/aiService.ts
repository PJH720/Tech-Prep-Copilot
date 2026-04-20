import { GoogleGenAI } from "@google/genai";
import OpenAI from "openai";
import { ResumeData, JDData, GapAnalysis, InterviewMessage, CompanyInfo, RagInsights, SourceItem, AgentBrief } from "../types";
import { BackendHealth } from "../lib/store";

// Gemini — VITE_GOOGLE_API_KEY가 있으면 활성화
const GEMINI_KEY = import.meta.env.VITE_GOOGLE_API_KEY || "";
const geminiClient = GEMINI_KEY ? new GoogleGenAI({ apiKey: GEMINI_KEY }) : null;
const GEMINI_MODEL = "gemini-2.5-flash-lite";

// OpenAI — OPENAI_API_KEY가 있으면 활성화 (팀원 호환)
const OPENAI_KEY = process.env.OPENAI_API_KEY || "";
const openaiClient = OPENAI_KEY
  ? new OpenAI({ apiKey: OPENAI_KEY, dangerouslyAllowBrowser: true })
  : null;

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
const BACKEND_TIMEOUT_MS = 4500;
const INTERVIEW_TURN_TIMEOUT_MS = 30000;
const COMPANY_KEYWORDS: Record<string, string[]> = {
  toss: ["toss", "toss.tech", "toss.im"],
  kakao: ["kakao", "tech.kakao.com"],
  naver: ["naver", "d2.naver.com"],
  coupang: ["coupang", "medium.com"],
};

const DEFAULT_INTERVIEW_QUESTION = "가장 인상 깊었던 프로젝트에 대해 말씀해 주시겠어요?";

/** PDF 추출 텍스트에 포함될 수 있는 lone surrogate(\uD800-\uDFFF) 제거 */
const stripSurrogates = (text: string): string => text.replace(/[\uD800-\uDFFF]/g, '');

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
    throw new Error(`LLM으로부터 빈 응답을 받았습니다 (${context}).`);
  }
  return content;
};

const parseJsonOrThrow = <T>(content: string, context: string): T => {
  try {
    return JSON.parse(content) as T;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(`LLM JSON 파싱 실패 (${context}): ${message}`);
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

export const fetchBackendHealth = async (): Promise<BackendHealth | null> => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), BACKEND_TIMEOUT_MS);
  try {
    const res = await fetch(`${BACKEND_URL}/api/health`, {
      method: "GET",
      signal: controller.signal,
    });
    if (!res.ok) return null;
    const data = (await res.json()) as Partial<BackendHealth>;
    if (typeof data.status !== "string") return null;
    return {
      status: data.status,
      rag_ready: Boolean(data.rag_ready),
      chunk_count: typeof data.chunk_count === "number" ? data.chunk_count : 0,
      tavily_ready: Boolean(data.tavily_ready),
      llm_provider_order:
        typeof data.llm_provider_order === "string" ? data.llm_provider_order : "",
      llm_gemini_configured: Boolean(data.llm_gemini_configured),
      llm_openai_configured: Boolean(data.llm_openai_configured),
      llm_upstage_configured: Boolean(data.llm_upstage_configured),
    };
  } catch {
    return null;
  } finally {
    clearTimeout(timeoutId);
  }
};

const generateJsonContent = async (
  systemInstruction: string,
  userPrompt: string,
  context: string
): Promise<string> => {
  // VITE_GOOGLE_API_KEY 우선 사용, 없으면 OPENAI_API_KEY fallback
  if (geminiClient) {
    const response = await geminiClient.models.generateContent({
      model: GEMINI_MODEL,
      config: { systemInstruction, responseMimeType: "application/json" },
      contents: userPrompt,
    });
    return assertNonEmptyContent(response.text, context);
  }
  if (openaiClient) {
    const response = await openaiClient.chat.completions.create({
      model: "gpt-4o-mini",
      messages: [
        { role: "system", content: systemInstruction },
        { role: "user", content: userPrompt },
      ],
      response_format: { type: "json_object" },
    });
    return assertNonEmptyContent(response.choices[0].message.content, context);
  }
  throw new Error(`LLM API 키가 설정되지 않았습니다 (${context}). VITE_GOOGLE_API_KEY 또는 OPENAI_API_KEY를 .env에 설정하세요.`);
};

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
    query: stripSurrogates(query),
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
  };
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
    ? `\n    검색된 엔지니어링 컨텍스트:\n    ${rag.contextText}\n    `
    : "";

  const prompt = `
    당신은 10년 경력의 IT 채용 컨설턴트입니다.
    아래 이력서와 채용공고(JD)를 비교하여 강점, 약점, 개선 권고사항을 분석하고 매칭 점수(0~100)를 제공하세요.
    반드시 한국어로 분석하세요.
    ${ragSection}

    이력서:
    ${resume.text}

    채용공고(JD):
    ${jd.text}

    반드시 다음 JSON 형식으로만 답변하세요:
    {
      "strengths": string[],
      "weaknesses": string[],
      "recommendations": string[],
      "matchScore": number
    }
  `;

  const responseText = await generateJsonContent(
    "당신은 시니어 IT 채용 컨설턴트입니다. 제공된 엔지니어링 컨텍스트를 근거로 분석하고, 확인되지 않은 회사 정보는 추측하지 마세요. 반드시 한국어로 답변하고, 유효한 JSON만 반환하세요.",
    prompt,
    "analyzeGap"
  );

  const parsed = parseJsonOrThrow<unknown>(responseText, "analyzeGap");
  if (!isGapAnalysis(parsed)) {
    throw new Error("analyzeGap: LLM 응답 스키마가 올바르지 않습니다.");
  }

  return {
    analysis: parsed,
    sources: rag.sources,
    ragAvailable: rag.ragAvailable,
  };
};

// ── 인터뷰 질문 생성 (백엔드 페르소나 엔드포인트 사용) ────────────────────────
export const generateInterviewQuestion = async (
  resume: ResumeData,
  company: CompanyInfo,
  history: InterviewMessage[],
  contextSummary?: string,
  recentAssistantQuestions: string[] = [],
  personaId: string = "dual-strict",
  activeChar: "interviewer" | "feedback_giver" = "interviewer"
): Promise<string> => {
  const resolvedContextSummary =
    contextSummary ||
    (
      await getAgentBrief(
        `${company.name} interview question context ${(history.map(m => m.content).join(" ") || resume.text).slice(0, 700)}`,
        company.id
      )
    )?.summary;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), BACKEND_TIMEOUT_MS);

  try {
    const res = await fetch(`${BACKEND_URL}/api/interview/question`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resume_text: stripSurrogates(resume.text),
        company_name: company.name,
        company_tech_stack: company.recentTechStack,
        company_description: company.description,
        history: history.map((m) => ({ role: m.role, content: stripSurrogates(m.content) })),
        persona_id: personaId,
        active_char: activeChar,
        context_summary: stripSurrogates(resolvedContextSummary || ""),
        recent_questions: recentAssistantQuestions.map(stripSurrogates),
      }),
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`Backend error: ${res.status}`);
    const data = await res.json();
    return (data.question as string).trim() || DEFAULT_INTERVIEW_QUESTION;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`면접 질문 생성 실패: ${message}`);
    return DEFAULT_INTERVIEW_QUESTION;
  } finally {
    clearTimeout(timeoutId);
  }
};

// ── 답변 평가 (백엔드 페르소나 엔드포인트 사용) ──────────────────────────────
export const evaluateAnswer = async (
  question: string,
  answer: string,
  company: CompanyInfo,
  contextSummary?: string,
  personaId: string = "dual-strict",
  activeChar: "interviewer" | "feedback_giver" = "interviewer"
): Promise<InterviewMessage["feedback"]> => {
  const resolvedContextSummary =
    contextSummary ||
    (
      await getAgentBrief(
        `${company.name} evaluate interview answer. Question: ${question}. Answer: ${answer}`.slice(0, 900),
        company.id
      )
    )?.summary;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), BACKEND_TIMEOUT_MS);

  try {
    const res = await fetch(`${BACKEND_URL}/api/interview/evaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        answer,
        company_name: company.name,
        company_tech_stack: company.recentTechStack,
        persona_id: personaId,
        active_char: activeChar,
        context_summary: resolvedContextSummary || "",
      }),
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`Backend error: ${res.status}`);
    const data = await res.json();
    if (!isInterviewFeedback(data)) {
      throw new Error("응답 스키마가 올바르지 않습니다.");
    }
    return data;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`답변 평가 실패: ${message}`);
    return { accuracy: 0, logic: 0, suggestion: "평가 중 오류가 발생했습니다.", referenceQuote: "" };
  } finally {
    clearTimeout(timeoutId);
  }
};

// ── 통합 턴 처리 (evaluate + next question = Gemini 1회) ─────────────────────
export const interviewTurn = async (
  resume: ResumeData,
  company: CompanyInfo,
  history: InterviewMessage[],
  lastQuestion: string,
  userAnswer: string,
  contextSummary: string,
  recentQuestions: string[],
  personaId: string,
  feedbackChar: "interviewer" | "feedback_giver",
  nextChar: "interviewer" | "feedback_giver"
): Promise<{
  feedback: InterviewMessage["feedback"];
  nextQuestion: string;
  nextAskedBy: "interviewer" | "feedback_giver";
} | null> => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), INTERVIEW_TURN_TIMEOUT_MS);
  try {
    const res = await fetch(`${BACKEND_URL}/api/interview/turn`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resume_text: stripSurrogates(resume.text),
        company_name: company.name,
        company_tech_stack: company.recentTechStack,
        company_description: company.description,
        history: history.map((m) => ({ role: m.role, content: stripSurrogates(m.content) })),
        persona_id: personaId,
        feedback_char: feedbackChar,
        next_char: nextChar,
        context_summary: stripSurrogates(contextSummary),
        recent_questions: recentQuestions.map(stripSurrogates),
        last_question: stripSurrogates(lastQuestion),
        user_answer: stripSurrogates(userAnswer),
      }),
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`Backend error: ${res.status}`);
    const data = await res.json();
    return {
      feedback: {
        accuracy: data.feedback_accuracy,
        logic: data.feedback_logic,
        suggestion: data.feedback_suggestion,
        referenceQuote: data.feedback_reference_quote,
      },
      nextQuestion: data.next_question,
      nextAskedBy: data.next_asked_by as "interviewer" | "feedback_giver",
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`인터뷰 턴 처리 실패: ${message}`);
    return null;
  } finally {
    clearTimeout(timeoutId);
  }
};
