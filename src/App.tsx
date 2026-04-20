import { useState } from 'react';
import { ResumeUploader } from './components/ResumeUploader';
import { JDInput } from './components/JDInput';
import { GapReport } from './components/GapReport';
import { InterviewChat } from './components/InterviewChat';
import { CompanySelector } from './components/CompanySelector';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './components/ui/tabs';
import { useAppStore } from './lib/store';
import { Rocket, FileSearch, MessageSquare, Building2 } from 'lucide-react';
import { motion } from 'motion/react';

export default function App() {
  const { analysis, resume, selectedCompany } = useAppStore();
  const [activeTab, setActiveTab] = useState('analyze');

  return (
    <div className="min-h-screen bg-slate-50/50 text-slate-900 font-sans">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b bg-white/80 backdrop-blur-md">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-10 h-10 bg-primary rounded-xl flex items-center justify-center shadow-lg shadow-primary/20">
              <Rocket className="text-white w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">Tech-Prep Copilot</h1>
              <p className="text-[10px] text-muted-foreground uppercase tracking-widest font-semibold">AI Career Agent</p>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 max-w-6xl">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* Sidebar / Setup */}
          <div className="lg:col-span-4 space-y-6">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="space-y-6"
            >
              <ResumeUploader />
              <CompanySelector />
            </motion.div>
          </div>

          {/* Main Content Area */}
          <div className="lg:col-span-8">
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
              <TabsList className="grid w-full grid-cols-2 mb-8 h-12">
                <TabsTrigger value="analyze" className="flex items-center gap-2 text-sm font-medium">
                  <FileSearch className="w-4 h-4" />
                  GAP Analysis
                </TabsTrigger>
                <TabsTrigger value="interview" className="flex items-center gap-2 text-sm font-medium">
                  <MessageSquare className="w-4 h-4" />
                  Mock Interview
                </TabsTrigger>
              </TabsList>

              <TabsContent value="analyze" className="space-y-8 mt-0">
                <JDInput />
                {analysis ? (
                  <GapReport />
                ) : (
                  <div className="flex flex-col items-center justify-center p-12 text-center bg-white border rounded-2xl shadow-sm">
                    <div className="w-16 h-16 bg-muted/30 rounded-full flex items-center justify-center mb-4">
                      <FileSearch className="w-8 h-8 text-muted-foreground opacity-30" />
                    </div>
                    <h3 className="text-lg font-semibold mb-2">Ready to Analyze?</h3>
                    <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                      Upload your resume and paste a job description to see how well you match the role.
                    </p>
                  </div>
                )}
              </TabsContent>

              <TabsContent value="interview" className="mt-0">
                <InterviewChat />
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t bg-white py-8 mt-20">
        <div className="container mx-auto px-4 text-center">
          <p className="text-sm text-muted-foreground">
            &copy; 2026 Tech-Prep Copilot. All rights reserved.
          </p>
          <div className="flex items-center justify-center gap-4 mt-4">
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <Building2 className="w-3 h-3" />
              RAG-based Company Analysis
            </div>
            <div className="w-1 h-1 rounded-full bg-muted-foreground/30" />
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <Rocket className="w-3 h-3" />
              AI-Powered Feedback
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

