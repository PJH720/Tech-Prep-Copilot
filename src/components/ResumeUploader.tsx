import React, { useCallback, useState } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import { Upload, FileText, Loader2, CheckCircle2 } from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { useAppStore } from '../lib/store';

// Use the bundled worker to avoid CDN/version/network issues.
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

export const ResumeUploader: React.FC = () => {
  const { resume, setResume } = useAppStore();
  const [isParsing, setIsParsing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onFileChange = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (file.type !== 'application/pdf') {
      setError('Please upload a PDF file.');
      return;
    }

    setIsParsing(true);
    setError(null);

    try {
      const arrayBuffer = await file.arrayBuffer();
      const pdf = await pdfjsLib.getDocument({ data: new Uint8Array(arrayBuffer) }).promise;
      let fullText = '';

      for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i);
        const textContent = await page.getTextContent();
        const pageText = textContent.items
          .map((item: any) => item.str)
          .join(' ');
        fullText += pageText + '\n';
      }

      setResume({
        text: fullText,
        name: file.name,
        parsedAt: new Date().toISOString(),
      });
    } catch (err) {
      console.error('Error parsing PDF:', err);
      setError('Failed to parse PDF. Please try again or copy-paste text.');
    } finally {
      setIsParsing(false);
    }
  }, [setResume]);

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-primary" />
          Resume Upload
        </CardTitle>
        <CardDescription>
          Upload your resume in PDF format to start the analysis.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col items-center justify-center border-2 border-dashed border-muted-foreground/25 rounded-lg p-8 transition-colors hover:border-primary/50">
          {resume ? (
            <div className="flex flex-col items-center gap-4 text-center">
              <CheckCircle2 className="w-12 h-12 text-green-500" />
              <div>
                <p className="font-medium text-lg">{resume.name}</p>
                <p className="text-sm text-muted-foreground">
                  Uploaded on {new Date(resume.parsedAt).toLocaleDateString()}
                </p>
              </div>
              <Button variant="outline" onClick={() => setResume(null)}>
                Change File
              </Button>
            </div>
          ) : (
            <>
              <Upload className="w-12 h-12 text-muted-foreground mb-4" />
              <p className="text-sm text-muted-foreground mb-4 text-center">
                Drag and drop your PDF here, or click to browse
              </p>
              <input
                type="file"
                accept=".pdf"
                onChange={onFileChange}
                className="hidden"
                id="resume-upload"
              />
              <Button asChild disabled={isParsing}>
                <label htmlFor="resume-upload" className="cursor-pointer">
                  {isParsing ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Parsing PDF...
                    </>
                  ) : (
                    'Select PDF'
                  )}
                </label>
              </Button>
            </>
          )}
          {error && <p className="mt-4 text-sm text-destructive">{error}</p>}
        </div>
      </CardContent>
    </Card>
  );
};
