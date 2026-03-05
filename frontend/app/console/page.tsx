'use client';

import { useStore } from '@/store';
import { Card } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { AlertCircle, Terminal } from 'lucide-react';
import Link from 'next/link';

// Import task modules
import { ChatModule } from '@/components/task/ChatModule';
import { ClassificationModule } from '@/components/task/ClassificationModule';
import { QAModule } from '@/components/task/QAModule';
import { VisionModule } from '@/components/task/VisionModule';
import { AudioModule } from '@/components/task/AudioModule';
import { EmbeddingModule } from '@/components/task/EmbeddingModule';
import { ModeSwitcher } from '@/components/chat/ModeSwitcher';

import { useEffect } from 'react';
import { api } from '@/lib/api';

export default function ConsolePage() {
  const { 
    systemStatus, setSystemStatus,
    taskType, setTaskType,
    isGenerative, setIsGenerative,
    executionMode, setExecutionMode,
    currentModel, setCurrentModel 
  } = useStore();

  useEffect(() => {
    const syncStatus = async () => {
      try {
        const [status, current] = await Promise.all([
          api.getSystemStatus(),
          api.getCurrentModel() as any
        ]);
        
        setSystemStatus(status as any);
        if (current.loaded) {
          setCurrentModel(current.model);
          setTaskType(current.task_type);
          setExecutionMode(current.mode);
          setIsGenerative(current.is_generative || current.task_type === 'causal_lm');
        }
      } catch (e) {
        console.error('Failed to sync console status:', e);
      }
    };
    
    syncStatus();
  }, [setSystemStatus, setCurrentModel, setTaskType, setExecutionMode, setIsGenerative]);

  if (!systemStatus?.model_loaded) {
    return (
      <div className="flex items-center justify-center h-full">
        <Card className="p-6 max-w-md">
          <Alert className="bg-destructive/10 border-destructive/20">
            <AlertCircle className="h-4 w-4 text-destructive" />
            <AlertDescription className="text-destructive">
              No model is currently loaded. Please load a model to begin execution tasks.
            </AlertDescription>
          </Alert>
          <Link href="/models" className="mt-4 block">
            <Button className="w-full">Select & Load a Task Model</Button>
          </Link>
        </Card>
      </div>
    );
  }

  // Derive active states from systemStatus if store is out of sync
  const activeTask = taskType || systemStatus?.task_type || "unknown";
  const activeModel = currentModel || systemStatus?.current_model || "Unknown Model";
  const activeMode = executionMode || systemStatus?.current_mode || "auto";
  
  // Robust generative detection (Heuristics for offline models)
  const isCausalTask = activeTask === 'causal_lm' || activeTask === 'seq2seq_lm';
  const hasChatPattern = activeModel.toLowerCase().includes('instruct') || 
                        activeModel.toLowerCase().includes('chat') || 
                        activeModel.toLowerCase().includes('llama') || 
                        activeModel.toLowerCase().includes('qwen') || 
                        activeModel.toLowerCase().includes('mistral') || 
                        activeModel.toLowerCase().includes('phi') ||
                        activeModel.toLowerCase().includes('bitnet');
                        
  const activeIsGen = isGenerative || systemStatus?.is_generative || isCausalTask || (activeTask === 'unknown' && hasChatPattern) || (activeTask === 'unknown' && activeModel !== "Unknown Model");

  return (
    <div className="flex flex-col h-full space-y-4">
      {/* Top Status Bar Change */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Terminal className="h-6 w-6" />
            Universal Execution Console
          </h1>
          <div className="text-sm text-muted-foreground flex items-center gap-2 mt-1">
             <span className="font-semibold px-2 py-0.5 bg-primary/10 rounded-full text-primary">Model: {activeModel}</span>
             <span className="font-semibold px-2 py-0.5 bg-secondary rounded-full text-secondary-foreground">Task: {activeIsGen && activeTask === 'unknown' ? 'Generative Chat' : activeTask.replace(/_/g, ' ')}</span>

             <span className="font-semibold px-2 py-0.5 bg-muted rounded-full">Mode: {activeMode}</span>
          </div>
        </div>
        
        {/* Mode Switch UI conditional rendering */}
        <div className="flex items-center gap-4">
          <ModeSwitcher />
        </div>
      </div>

      {/* Dynamic Task Rendering */}
      <div className="flex-1 flex flex-col min-h-0 bg-card rounded-2xl border shadow-sm overflow-hidden">
         {activeIsGen && 
            <ChatModule 
                taskType={activeTask} 
                model={activeModel} 
            />
         }
         {!activeIsGen && activeTask.includes('classification') && !activeTask.includes('vision') && !activeTask.includes('audio') && !activeTask.includes('image') &&
            <ClassificationModule taskType={activeTask} />
         }
         {!activeIsGen && activeTask === 'question_answering' &&
            <QAModule />
         }
         {!activeIsGen && (activeTask.includes('image') || activeTask.includes('vision') || activeTask === 'object_detection') &&
            <VisionModule taskType={activeTask} />
         }
         {!activeIsGen && activeTask.includes('audio') &&
            <AudioModule taskType={activeTask} />
         }
         {!activeIsGen && activeTask === 'text_encoding' &&
            <EmbeddingModule />
         }
         
         {!activeIsGen && activeTask !== 'unknown' && !activeTask.includes('classification') && activeTask !== 'question_answering' && !activeTask.includes('vision') && !activeTask.includes('audio') && !activeTask.includes('image') && activeTask !== 'text_encoding' &&
            <div className="flex-1 flex flex-col justify-center items-center">
                <h2>No UI module exists for this explicit task yet ({activeTask}). However, you can still execute via API.</h2>
            </div>
         }

         {activeTask === 'unknown' && !activeIsGen && !systemStatus?.model_loaded &&
            <div className="flex-1 flex flex-col justify-center items-center opacity-50">
                <Terminal className="h-12 w-12 mb-4" />
                <h2 className="text-xl font-medium">Initializing Task Control...</h2>
                <p>Detecting model capabilities</p>
            </div>
         }

      </div>
    </div>
  );
}
