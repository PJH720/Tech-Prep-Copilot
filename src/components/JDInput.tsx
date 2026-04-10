import React from 'react';
import { Briefcase, Send } from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Textarea } from './ui/textarea';
import { useAppStore } from '../lib/store';
import { analyzeGap } from '../services/aiService';

export const JDInput: React.FC = () => {
  const { jd, setJD, resume, setAnalysis, setIsLoading, isLoading } = useAppStore();
  const [text, setText] = React.useState(jd?.text || '');

  const handleAnalyze = async () => {
    if (!resume || !text) return;
    
    setIsLoading(true);
    try {
      const jdData = { text };
      setJD(jdData);
      const result = await analyzeGap(resume, jdData);
      setAnalysis(result);
    } catch (err) {
      console.error('Analysis failed:', err);
    } finally {
      setIsLoading(false);
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
        <Textarea
          placeholder="Paste JD here..."
          className="min-h-[200px] resize-none"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <Button 
          className="w-full" 
          disabled={!resume || !text || isLoading}
          onClick={handleAnalyze}
        >
          {isLoading ? 'Analyzing...' : 'Analyze Fit'}
          <Send className="ml-2 w-4 h-4" />
        </Button>
        {!resume && (
          <p className="text-xs text-muted-foreground text-center">
            Upload your resume first to enable analysis.
          </p>
        )}
      </CardContent>
    </Card>
  );
};
