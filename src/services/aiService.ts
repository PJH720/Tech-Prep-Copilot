import { GoogleGenAI, Type } from "@google/genai";
import { ResumeData, JDData, GapAnalysis, InterviewMessage, CompanyInfo } from "../types";

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY || "" });

export const analyzeGap = async (resume: ResumeData, jd: JDData): Promise<GapAnalysis> => {
  const model = "gemini-3-flash-preview";
  const prompt = `
    You are a 10-year experienced IT recruitment consultant.
    Compare the following Resume and Job Description (JD).
    Analyze the strengths, weaknesses, and provide recommendations for the candidate.
    Also, provide a match score from 0 to 100.

    Resume:
    ${resume.text}

    Job Description:
    ${jd.text}

    Return the analysis in JSON format.
  `;

  const response = await ai.models.generateContent({
    model,
    contents: prompt,
    config: {
      responseMimeType: "application/json",
      responseSchema: {
        type: Type.OBJECT,
        properties: {
          strengths: { type: Type.ARRAY, items: { type: Type.STRING } },
          weaknesses: { type: Type.ARRAY, items: { type: Type.STRING } },
          recommendations: { type: Type.ARRAY, items: { type: Type.STRING } },
          matchScore: { type: Type.NUMBER },
        },
        required: ["strengths", "weaknesses", "recommendations", "matchScore"],
      },
    },
  });

  return JSON.parse(response.text);
};

export const generateInterviewQuestion = async (
  resume: ResumeData,
  company: CompanyInfo,
  history: InterviewMessage[]
): Promise<string> => {
  const model = "gemini-3-flash-preview";
  const historyText = history.map(m => `${m.role}: ${m.content}`).join("\n");
  
  const prompt = `
    You are a senior engineer interviewer at ${company.name}.
    Company Tech Stack: ${company.recentTechStack.join(", ")}
    Company Description: ${company.description}

    Candidate Resume:
    ${resume.text}

    Interview History:
    ${historyText}

    Based on the candidate's resume and the company's technical interests, ask a deep technical follow-up question.
    Focus on one of their projects and how it relates to the company's tech stack.
    Be professional and challenging.
  `;

  const response = await ai.models.generateContent({
    model,
    contents: prompt,
  });

  return response.text || "Could you tell me more about your most significant project?";
};

export const evaluateAnswer = async (
  question: string,
  answer: string,
  company: CompanyInfo
): Promise<InterviewMessage['feedback']> => {
  const model = "gemini-3-flash-preview";
  const prompt = `
    You are a senior engineer interviewer at ${company.name}.
    Evaluate the candidate's answer to your question.
    
    Question: ${question}
    Answer: ${answer}

    Provide feedback on technical accuracy (0-100), logic (0-100), and a suggestion for improvement.
    If possible, include a reference quote or concept that the company values (based on their tech stack: ${company.recentTechStack.join(", ")}).

    Return the evaluation in JSON format.
  `;

  const response = await ai.models.generateContent({
    model,
    contents: prompt,
    config: {
      responseMimeType: "application/json",
      responseSchema: {
        type: Type.OBJECT,
        properties: {
          accuracy: { type: Type.NUMBER },
          logic: { type: Type.NUMBER },
          suggestion: { type: Type.STRING },
          referenceQuote: { type: Type.STRING },
        },
        required: ["accuracy", "logic", "suggestion"],
      },
    },
  });

  return JSON.parse(response.text);
};
