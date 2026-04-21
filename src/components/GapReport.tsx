import React from 'react';
import { CheckCircle2, AlertCircle, Lightbulb, Target } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Progress } from './ui/progress';
import { Badge } from './ui/badge';
import { useAppStore } from '../lib/store';
import { motion } from 'motion/react';

export const GapReport: React.FC = () => {
  const { analysis, analysisSources, analysisRagAvailable, backendHealth, selectedCompany } = useAppStore();

  if (!analysis) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      <Card className="overflow-hidden border-primary/20 bg-primary/5">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Target className="w-5 h-5 text-primary" />
              Match Score
            </div>
            <span className="text-3xl font-bold text-primary">{analysis.matchScore}%</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Progress value={analysis.matchScore} className="h-3" />
          <p className="mt-2 text-sm text-muted-foreground">
            Based on your resume and the provided job description.
          </p>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-green-600">
              <CheckCircle2 className="w-5 h-5" />
              Strengths
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {analysis.strengths.map((s, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <Badge variant="outline" className="mt-0.5 bg-green-50 text-green-700 border-green-200">
                    {i + 1}
                  </Badge>
                  {s}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-amber-600">
              <AlertCircle className="w-5 h-5" />
              Weaknesses
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {analysis.weaknesses.map((w, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <Badge variant="outline" className="mt-0.5 bg-amber-50 text-amber-700 border-amber-200">
                    {i + 1}
                  </Badge>
                  {w}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>

      <Card className="border-blue-200 bg-blue-50/30">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-blue-700">
            <Lightbulb className="w-5 h-5" />
            Recommendations
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {analysis.recommendations.map((r, i) => (
              <li key={i} className="flex items-center gap-2 text-sm text-blue-900 bg-white/50 p-3 rounded-lg border border-blue-100">
                <div className="w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0" />
                {r}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">참고한 기술 블로그 (Relevance Score)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {analysisSources.length === 0 ? (
            <div className="text-sm text-muted-foreground space-y-1">
              {!selectedCompany ? (
                <>
                  <p>대상 기업을 선택하지 않아 기술 블로그 참조를 건너뛰었습니다.</p>
                  <p className="text-xs">왼쪽에서 기업을 선택한 뒤 다시 분석하면 Relevance Score가 표시됩니다.</p>
                </>
              ) : !backendHealth ? (
                <>
                  <p>백엔드에 연결할 수 없어 RAG 검색이 실행되지 않았습니다.</p>
                  <p className="text-xs">FastAPI 백엔드를 실행하세요: python -m uvicorn backend.main:app --port 8000</p>
                </>
              ) : !backendHealth.rag_ready ? (
                <>
                  <p>ChromaDB가 로드되지 않아 Relevance Score를 표시할 수 없습니다.</p>
                  <p className="text-xs">
                    {backendHealth.rag_setup_hint || '백엔드를 재시작하거나 README의 벡터 DB 설정 안내를 참조하세요.'}
                  </p>
                </>
              ) : (
                <>
                  <p>RAG 검색 결과가 비어 있습니다. (유사도 기준 미달)</p>
                  <p className="text-xs">검색 쿼리와 일치하는 기술 블로그 콘텐츠를 찾지 못했습니다.</p>
                </>
              )}
            </div>
          ) : (
            analysisSources.slice(0, 5).map((source, index) => {
              const rawScore = typeof source.score === 'number' ? source.score : 0;
              const scorePct = Math.round(Math.max(0, Math.min(1, rawScore)) * 100);
              const tier =
                rawScore >= 0.7 ? 'high' : rawScore >= 0.5 ? 'mid' : 'low';
              const tierStyle = {
                high: 'bg-green-50 text-green-700 border-green-200',
                mid: 'bg-amber-50 text-amber-700 border-amber-200',
                low: 'bg-slate-50 text-slate-600 border-slate-200',
              }[tier];
              const tierLabel = { high: '높음', mid: '보통', low: '낮음' }[tier];

              return (
                <div
                  key={`${source.source}-${index}`}
                  className="rounded-md border p-3 text-sm space-y-2"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-medium flex-1">{source.title || 'Untitled Source'}</p>
                    <Badge variant="outline" className={tierStyle}>
                      관련도 {tierLabel} · {scorePct}%
                    </Badge>
                  </div>
                  <Progress value={scorePct} className="h-1.5" />
                  {source.content && (
                    <p className="text-xs text-muted-foreground line-clamp-2">
                      {source.content}
                    </p>
                  )}
                  {source.source && (
                    <a
                      href={source.source}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-600 hover:underline break-all"
                    >
                      {source.source}
                    </a>
                  )}
                </div>
              );
            })
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
};
