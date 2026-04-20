import React from 'react';
import { Briefcase, Send } from 'lucide-react';
import { AlertCircle, CheckCircle2, RefreshCw, ServerCrash } from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Textarea } from './ui/textarea';
import { useAppStore } from '../lib/store';
import { analyzeGap, fetchBackendHealth } from '../services/aiService';
import { Badge } from './ui/badge';

export const JDInput: React.FC = () => {
  const {
    jd,
    setJD,
    resume,
    selectedCompany,
    setAnalysis,
    setAnalysisSources,
    analysisError,
    setAnalysisError,
    backendHealth,
    setBackendHealth,
    setIsAnalyzing,
    isAnalyzing
  } = useAppStore();
  const [isHealthChecking, setIsHealthChecking] = React.useState(false);
  // Sync local text with store — handles external resets (e.g. resetAll())
  const [text, setText] = React.useState(jd?.text || '');
  React.useEffect(() => {
    setText(jd?.text || '');
  }, [jd]);

  const checkBackendHealth = React.useCallback(async () => {
    setIsHealthChecking(true);
    try {
      const health = await fetchBackendHealth();
      setBackendHealth(health);
    } finally {
      setIsHealthChecking(false);
    }
  }, [setBackendHealth]);

  React.useEffect(() => {
    void checkBackendHealth();
  }, [checkBackendHealth]);

  const handleAnalyze = async () => {
    if (!resume || !text) return;

    setAnalysisError(null);
    setAnalysis(null);
    setAnalysisSources([]);
    setIsAnalyzing(true);
    try {
      const jdData = { text };
      setJD(jdData);
      const result = await analyzeGap(resume, jdData, selectedCompany ?? undefined);
      setAnalysis(result.analysis);
      setAnalysisSources(result.sources);
      setAnalysisError(null);
    } catch (err) {
      console.error('Analysis failed:', err);
      const message = err instanceof Error ? err.message : '분석 중 알 수 없는 오류가 발생했습니다.';
      setAnalysisError(message);
    } finally {
      setIsAnalyzing(false);
      void checkBackendHealth();
    }
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Briefcase className="w-5 h-5 text-primary" />
          Job Description
        </CardTitle>
        <CardDescription>
          Paste the job description of the role you're applying for.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-lg border bg-slate-50 p-3 space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-slate-700">Runtime Status</p>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void checkBackendHealth()}
              disabled={isHealthChecking}
            >
              <RefreshCw className={`mr-1 h-3.5 w-3.5 ${isHealthChecking ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant={backendHealth ? 'default' : 'destructive'}>
              {backendHealth ? 'Backend connected' : 'Backend disconnected'}
            </Badge>
            <Badge variant={backendHealth?.rag_ready ? 'default' : 'secondary'}>
              {backendHealth?.rag_ready ? `RAG ready (${backendHealth.chunk_count})` : 'RAG missing'}
            </Badge>
            <Badge
              variant={
                backendHealth &&
                (backendHealth.llm_gemini_configured ||
                  backendHealth.llm_openai_configured ||
                  backendHealth.llm_upstage_configured)
                  ? 'default'
                  : 'secondary'
              }
            >
              {backendHealth &&
              (backendHealth.llm_gemini_configured ||
                backendHealth.llm_openai_configured ||
                backendHealth.llm_upstage_configured)
                ? 'LLM configured'
                : 'LLM missing'}
            </Badge>
          </div>
        </div>
        <Textarea
          placeholder="Paste JD here..."
          className="min-h-[200px] resize-none"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <Button 
          className="w-full" 
          disabled={!resume || !text || isAnalyzing}
          onClick={handleAnalyze}
        >
          {isAnalyzing ? 'Analyzing...' : 'Analyze Fit'}
          <Send className="ml-2 w-4 h-4" />
        </Button>
        {analysisError && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3">
            <p className="flex items-start gap-2 text-sm text-destructive">
              <ServerCrash className="mt-0.5 h-4 w-4 shrink-0" />
              <span>분석 실패: {analysisError}</span>
            </p>
            <p className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
              <AlertCircle className="h-3.5 w-3.5" />
              백엔드 연결/LLM 키 설정/입력값을 확인한 뒤 다시 시도해주세요.
            </p>
          </div>
        )}
        {!analysisError && !isAnalyzing && resume && text && (
          <p className="flex items-center gap-2 text-xs text-muted-foreground">
            <CheckCircle2 className="h-3.5 w-3.5" />
            실행 상태는 위 Runtime Status에서 실시간으로 확인할 수 있습니다.
          </p>
        )}
        {!resume && (
          <p className="text-xs text-muted-foreground text-center">
            Upload your resume first to enable analysis.
          </p>
        )}
      </CardContent>
    </Card>
  );
};
