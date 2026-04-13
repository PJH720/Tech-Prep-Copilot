import React, { useState, useRef, useEffect } from 'react';
import { cn } from '../lib/utils';
import { MessageSquare, Send, User, Bot, Loader2, RefreshCw, Quote } from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from './ui/card';
import { ScrollArea } from './ui/scroll-area';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { Separator } from './ui/separator';
import { useAppStore } from '../lib/store';
import { generateInterviewQuestion, evaluateAnswer, getAgentBrief } from '../services/aiService';
import { InterviewMessage } from '../types';
import { motion, AnimatePresence } from 'motion/react';

export const InterviewChat: React.FC = () => {
  const {
    resume,
    selectedCompany,
    interviewHistory,
    addInterviewMessage,
    setInterviewHistory,
    isInterviewing: isLoading,
    setIsInterviewing: setIsLoading
  } = useAppStore();
  
  const [input, setInput] = useState('');
  // Refs: bottomAnchor for auto-scroll; historyRef to avoid stale closure in async handlers
  const bottomAnchorRef = useRef<HTMLDivElement>(null);
  const historyRef = useRef(interviewHistory);
  historyRef.current = interviewHistory;

  useEffect(() => {
    bottomAnchorRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [interviewHistory]);

  const startInterview = async () => {
    if (!resume || !selectedCompany) return;

    setIsLoading(true);
    setInterviewHistory([]);
    try {
      const brief = await getAgentBrief(
        selectedCompany.id,
        `${selectedCompany.name} interview starter question from resume context ${resume.text.slice(0, 400)}`
      );
      const contextSummary = brief?.summary;
      const question = await generateInterviewQuestion(resume, selectedCompany, [], contextSummary);
      addInterviewMessage({
        role: 'assistant',
        content: question,
        timestamp: new Date().toISOString(),
      });
    } catch (err) {
      console.error('Failed to start interview:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || !resume || !selectedCompany || isLoading) return;

    const userMessage: InterviewMessage = {
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };

    // Capture current history BEFORE any state mutations to avoid stale closures
    const currentHistory = historyRef.current;
    const lastAssistantMessage = [...currentHistory].reverse().find(m => m.role === 'assistant');

    addInterviewMessage(userMessage);
    setInput('');
    setIsLoading(true);

    try {
      const recentAssistantQuestions = currentHistory
        .filter((message) => message.role === 'assistant')
        .slice(-5)
        .map((message) => message.content);

      // 1. Build orchestration context (RAG + optional realtime search)
      const brief = await getAgentBrief(
        selectedCompany.id,
        `${lastAssistantMessage?.content ?? ''} ${input}`.slice(0, 800)
      );
      const contextSummary = brief?.summary;

      // 2. Evaluate current answer
      const feedback = await evaluateAnswer(
        lastAssistantMessage?.content || '',
        input,
        selectedCompany,
        contextSummary
      );

      // 3. Attach feedback to user message and write the full history atomically
      const historyWithFeedback: InterviewMessage[] = [
        ...currentHistory,
        { ...userMessage, feedback },
      ];
      setInterviewHistory(historyWithFeedback);

      // 4. Generate next question with updated history + RAG context
      const nextQuestion = await generateInterviewQuestion(
        resume,
        selectedCompany,
        historyWithFeedback,
        contextSummary,
        recentAssistantQuestions
      );
      addInterviewMessage({
        role: 'assistant',
        content: nextQuestion,
        timestamp: new Date().toISOString(),
      });
    } catch (err) {
      console.error('Failed to process message:', err);
    } finally {
      setIsLoading(false);
    }
  };

  if (!resume || !selectedCompany) {
    return (
      <Card className="flex flex-col items-center justify-center p-12 text-center bg-muted/30 border-dashed">
        <MessageSquare className="w-12 h-12 text-muted-foreground mb-4 opacity-20" />
        <h3 className="text-lg font-semibold mb-2">Interview Ready?</h3>
        <p className="text-sm text-muted-foreground max-w-xs">
          Please upload your resume and select a target company to start a mock interview.
        </p>
      </Card>
    );
  }

  return (
    <Card className="flex flex-col h-[600px]">
      <CardHeader className="border-bottom flex flex-row items-center justify-between py-4">
        <CardTitle className="flex items-center gap-2 text-lg">
          <MessageSquare className="w-5 h-5 text-primary" />
          Mock Interview: {selectedCompany.name}
        </CardTitle>
        <Button variant="ghost" size="sm" onClick={startInterview} disabled={isLoading}>
          <RefreshCw className={cn("w-4 h-4 mr-2", isLoading && "animate-spin")} />
          Reset
        </Button>
      </CardHeader>
      
      <CardContent className="flex-1 overflow-hidden p-0">
        <ScrollArea className="h-full p-4">
          {interviewHistory.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center py-12">
              <Bot className="w-12 h-12 text-primary mb-4" />
              <h3 className="font-semibold">Ready to start?</h3>
              <p className="text-sm text-muted-foreground mb-6">
                The AI will act as a senior engineer from {selectedCompany.name}.
              </p>
              <Button onClick={startInterview} disabled={isLoading}>
                {isLoading ? <Loader2 className="animate-spin mr-2" /> : null}
                Start Interview
              </Button>
            </div>
          ) : (
            <div className="space-y-6">
              <AnimatePresence initial={false}>
                {interviewHistory.map((msg, i) => (
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
                          <div className="flex items-center justify-between gap-4">
                            <div className="flex gap-2">
                              <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                                Accuracy: {msg.feedback.accuracy}%
                              </Badge>
                              <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
                                Logic: {msg.feedback.logic}%
                              </Badge>
                            </div>
                          </div>
                          <p className="text-xs text-muted-foreground italic">
                            <span className="font-semibold text-foreground not-italic">Feedback: </span>
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
                ))}
              </AnimatePresence>
              <div ref={bottomAnchorRef} />
              {isLoading && (
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
            placeholder={interviewHistory.length === 0 ? "Start the interview first..." : "Type your answer..."}
            className="min-h-[80px] resize-none"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            disabled={interviewHistory.length === 0 || isLoading}
          />
          <Button 
            size="icon" 
            className="h-[80px] w-[60px] shrink-0" 
            onClick={handleSend}
            disabled={!input.trim() || isLoading || interviewHistory.length === 0}
          >
            <Send className="w-5 h-5" />
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
};
