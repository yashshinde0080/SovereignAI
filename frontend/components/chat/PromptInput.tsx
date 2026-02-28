'use client';

import { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Send } from 'lucide-react';
import { cn } from '@/lib/utils';

interface PromptInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function PromptInput({ onSend, disabled }: PromptInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = () => {
    if (input.trim() && !disabled) {
      onSend(input.trim());
      setInput('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  return (
    <div className="relative flex items-end gap-2 bg-background border border-border shadow-sm rounded-2xl p-2 focus-within:ring-2 focus-within:ring-primary/20 focus-within:border-primary transition-all">
      <Textarea
        ref={textareaRef}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Message the model... (Shift+Enter for newline)"
        disabled={disabled}
        className="min-h-[44px] max-h-[200px] resize-none border-0 focus-visible:ring-0 shadow-none px-3 py-3 bg-transparent w-full text-[15px]"
        rows={1}
      />
      <div className="flex-shrink-0 h-11 flex items-center mb-[2px]">
        <Button 
          onClick={handleSubmit} 
          disabled={disabled || !input.trim()}
          size="icon"
          className={cn(
            "h-9 w-9 rounded-xl transition-all duration-300",
            input.trim() 
              ? "bg-primary text-primary-foreground hover:bg-primary/90 shadow-md scale-100" 
              : "bg-muted text-muted-foreground scale-95 opacity-50"
          )}
        >
          <Send className={cn("h-4 w-4", input.trim() && "ml-0.5")} />
        </Button>
      </div>
    </div>
  );
}