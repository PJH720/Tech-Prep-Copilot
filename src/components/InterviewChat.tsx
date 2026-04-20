import React, { useState, useRef, useEffect } from 'react';
import { cn } from '../lib/utils';
import { MessageSquare, Send, User, Bot, Loader2, RefreshCw, Quote } from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from './ui/card';
import { ScrollArea } from './ui/scroll-area';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { useAppStore } from '../lib/store';
import { generateInterviewQuestion, interviewTurn, getAgentBrief } from '../services/aiService';
import { InterviewMessage } from '../types';
import { motion, AnimatePresence } from 'motion/react';
import { PersonaSelector, PersonaInfo, PERSONAS } from './PersonaSelector';

export const InterviewChat: React.FC = () => {
  const {
    resume,
    selectedCompany,
    interviewHistory,
    addInterviewMessage,
    setInterviewHistory,
    isInterviewing,
    setIsInterviewing
  } = useAppStore();

  const [input, setInput] = useState('');
  const [selectedPersonaId, setSelectedPersonaId] = useState('dual-strict');
  const [loadedPersonas, setLoadedPersonas] = useState<PersonaInfo[]>(PERSONAS);
  const [interviewStarted, setInterviewStarted] = useState(false);
  const nextActiveCharRef = useRef<'interviewer' | 'feedback_giver'>('interviewer');

  const selectedPersona = loadedPersonas.find(p => p.id === selectedPersonaId) ?? loadedPersonas[0];

  const randomActiveChar = (): 'interviewer' | 'feedback_giver' =>
    Math.random() < 0.5 ? 'interviewer' : 'feedback_giver';

  const bottomAnchorRef = useRef<HTMLDivElement>(null);
  const historyRef = useRef(interviewHistory);

  useEffect(() => {
    historyRef.current = interviewHistory;
  }, [interviewHistory]);

  useEffect(() => {
    bottomAnchorRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [interviewHistory]);

  const startInterview = async () => {
    if (!resume || !selectedCompany) return;

    setIsInterviewing(true);
    setInterviewHistory([]);
    setInterviewStarted(true);
    try {
      const brief = await getAgentBrief(
        `${selectedCompany.name} interview starter question from resume context ${resume.text.slice(0, 400)}`,
        selectedCompany.id
      );
      const contextSummary = brief?.summary;
      const activeChar = randomActiveChar();
      const question = await generateInterviewQuestion(
        resume,
        selectedCompany,
        [],
        contextSummary,
        [],
        selectedPersonaId,
        activeChar
      );
      addInterviewMessage({
        role: 'assistant',
        content: question,
        timestamp: new Date().toISOString(),
        asked_by: activeChar,
      });
    } catch (err) {
      console.error('Failed to start interview:', err);
    } finally {
      setIsInterviewing(false);
    }
  };

  const handleReset = () => {
    setInterviewHistory([]);
    setInterviewStarted(false);
  };

  const handleSend = async () => {
    if (!input.trim() || !resume || !selectedCompany || isInterviewing) return;
    const submittedInput = input.trim();

    const userMessage: InterviewMessage = {
      role: 'user',
      content: submittedInput,
      timestamp: new Date().toISOString(),
    };

    const currentHistory = historyRef.current;
    const lastAssistantMessage = [...currentHistory].reverse().find(m => m.role === 'assistant');

    addInterviewMessage(userMessage);
    setInput('');
    setIsInterviewing(true);

    try {
      const recentAssistantQuestions = currentHistory
        .filter((message) => message.role === 'assistant')
        .slice(-5)
        .map((message) => message.content);

      const brief = await getAgentBrief(
        `${lastAssistantMessage?.content ?? ''} ${submittedInput}`.slice(0, 800),
        selectedCompany.id
      );
      const contextSummary = brief?.summary ?? '';

      const lastAskedBy = lastAssistantMessage?.asked_by ?? 'interviewer';
      const nextActiveChar = randomActiveChar();

      // 피드백 + 다음 질문을 Gemini 1회 호출로 처리
      const turnResult = await interviewTurn(
        resume,
        selectedCompany,
        currentHistory,
        lastAssistantMessage?.content ?? '',
        submittedInput,
        contextSummary,
        recentAssistantQuestions,
        selectedPersonaId,
        lastAskedBy,
        nextActiveChar
      );

      if (turnResult) {
        const historyWithFeedback: InterviewMessage[] = [
          ...currentHistory,
          { ...userMessage, feedback: turnResult.feedback },
        ];
        setInterviewHistory(historyWithFeedback);
        addInterviewMessage({
          role: 'assistant',
          content: turnResult.nextQuestion,
          timestamp: new Date().toISOString(),
          asked_by: turnResult.nextAskedBy,
        });
      }
    } catch (err) {
      console.error('Failed to process message:', err);
    } finally {
      setIsInterviewing(false);
    }
  };

  if (!resume || !selectedCompany) {
    return (
      <Card className="flex flex-col items-center justify-center p-12 text-center bg-muted/30 border-dashed">
        <MessageSquare className="w-12 h-12 text-muted-foreground mb-4 opacity-20" />
        <h3 className="text-lg font-semibold mb-2">면접 준비가 되셨나요?</h3>
        <p className="text-sm text-muted-foreground max-w-xs">
          이력서와 목표 회사를 선택하면 모의 면접을 시작할 수 있습니다.
        </p>
      </Card>
    );
  }

  return (
    <Card className="flex flex-col h-[680px]">
      <CardHeader className="border-b flex flex-row items-center justify-between py-4">
        <CardTitle className="flex items-center gap-2 text-lg">
          <MessageSquare className="w-5 h-5 text-primary" />
          <span>모의 면접: {selectedCompany.name}</span>
          {interviewStarted && selectedPersona && (
            <span className="text-xs font-normal text-muted-foreground border rounded-full px-2 py-0.5">
              {selectedPersona.emoji} {selectedPersona.name}
            </span>
          )}
        </CardTitle>
        <Button variant="ghost" size="sm" onClick={handleReset} disabled={isInterviewing}>
          <RefreshCw className={cn("w-4 h-4 mr-2", isInterviewing && "animate-spin")} />
          초기화
        </Button>
      </CardHeader>

      <CardContent className="flex-1 overflow-hidden p-0">
        <ScrollArea className="h-full p-4">
          {!interviewStarted ? (
            <div className="flex flex-col items-center justify-center h-full text-center py-8 gap-6">
              <div className="w-full max-w-md">
                <PersonaSelector
                  selectedPersonaId={selectedPersonaId}
                  onSelect={setSelectedPersonaId}
                  onPersonasLoaded={setLoadedPersonas}
                  disabled={isInterviewing}
                />
              </div>
              <Button onClick={startInterview} disabled={isInterviewing} size="lg">
                {isInterviewing ? <Loader2 className="animate-spin mr-2" /> : null}
                면접 시작
              </Button>
            </div>
          ) : (
            <div className="space-y-6">
              <AnimatePresence initial={false}>
                {interviewHistory.map((msg, i) => {
                  // 이 유저 메시지에 피드백을 준 캐릭터 = 직전 어시스턴트의 asked_by
                  const prevAskedBy = interviewHistory
                    .slice(0, i)
                    .reverse()
                    .find((m) => m.role === 'assistant')?.asked_by ?? 'interviewer';
                  const feedbackGiverName = selectedPersona
                    ? prevAskedBy === 'feedback_giver'
                      ? selectedPersona.feedback_character
                      : selectedPersona.interview_character
                    : '';
                  return (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: msg.role === 'user' ? 20 : -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    className={cn(
                      "flex gap-3 max-w-[85%]",
                      msg.role === 'user' ? "ml-auto flex-row-reverse" : "mr-auto"
                    )}
                  >
                    <div className={cn(
                      "w-8 h-8 rounded-full flex items-center justify-center shrink-0",
                      msg.role === 'user' ? "bg-primary text-primary-foreground" : "bg-muted"
                    )}>
                      {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
                    </div>
                    <div className="space-y-2">
                      {/* 발화자 이름 라벨 */}
                      {msg.role === 'assistant' && selectedPersona && (
                        <p className="text-[10px] text-muted-foreground font-medium pl-1">
                          {selectedPersona.emoji}{' '}
                          {msg.asked_by === 'feedback_giver'
                            ? selectedPersona.feedback_character
                            : selectedPersona.interview_character}
                        </p>
                      )}
                      <div className={cn(
                        "p-4 rounded-2xl text-sm leading-relaxed shadow-sm",
                        msg.role === 'user'
                          ? "bg-primary text-primary-foreground rounded-tr-none"
                          : "bg-muted/50 rounded-tl-none"
                      )}>
                        {msg.content}
                      </div>

                      {msg.feedback && (
                        <motion.div
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          className="bg-card border rounded-xl p-3 space-y-3 shadow-sm"
                        >
                          {/* 피드백 캐릭터 이름 */}
                          {selectedPersona && (
                            <p className="text-[10px] font-semibold text-green-700">
                              💬 {feedbackGiverName}
                            </p>
                          )}
                          <div className="flex gap-2">
                            <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                              정확도: {msg.feedback.accuracy}%
                            </Badge>
                            <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
                              논리: {msg.feedback.logic}%
                            </Badge>
                          </div>
                          <p className="text-xs text-muted-foreground italic">
                            <span className="font-semibold text-foreground not-italic">피드백: </span>
                            {msg.feedback.suggestion}
                          </p>
                          {msg.feedback.referenceQuote && (
                            <div className="bg-muted/30 p-2 rounded-lg border-l-2 border-primary/30 flex gap-2">
                              <Quote className="w-3 h-3 text-primary shrink-0 mt-1" />
                              <p className="text-[10px] text-muted-foreground leading-tight">
                                {msg.feedback.referenceQuote}
                              </p>
                            </div>
                          )}
                        </motion.div>
                      )}
                    </div>
                  </motion.div>
                  );
                })}
              </AnimatePresence>
              <div ref={bottomAnchorRef} />
              {isInterviewing && (
                <div className="flex gap-3 mr-auto">
                  <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                    <Bot size={16} />
                  </div>
                  <div className="bg-muted/50 p-4 rounded-2xl rounded-tl-none">
                    <Loader2 className="w-4 h-4 animate-spin" />
                  </div>
                </div>
              )}
            </div>
          )}
        </ScrollArea>
      </CardContent>

      <CardFooter className="p-4 border-t bg-muted/5">
        <div className="flex w-full gap-2">
          <Textarea
            placeholder={!interviewStarted ? "먼저 면접을 시작하세요..." : "답변을 입력하세요..."}
            className="min-h-[80px] resize-none"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            disabled={!interviewStarted || isInterviewing}
          />
          <Button
            size="icon"
            className="h-[80px] w-[60px] shrink-0"
            onClick={handleSend}
            disabled={!input.trim() || isInterviewing || !interviewStarted}
          >
            <Send className="w-5 h-5" />
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
};
