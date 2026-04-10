import React from 'react';
import { CheckCircle2, AlertCircle, Lightbulb, Target } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Progress } from './ui/progress';
import { Badge } from './ui/badge';
import { useAppStore } from '../lib/store';
import { motion } from 'motion/react';

export const GapReport: React.FC = () => {
  const { analysis } = useAppStore();

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
    </motion.div>
  );
};
