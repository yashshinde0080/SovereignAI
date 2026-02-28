'use client';

import { cn } from '@/lib/utils';
import { Message } from '@/types';
import { User, Bot, Copy, Check } from 'lucide-react';
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { motion, AnimatePresence } from 'framer-motion';

interface MessageListProps {
  messages: Message[];
}

const CodeBlock = ({ inline, className, children, ...props }: any) => {
  const [copied, setCopied] = useState(false);
  const match = /language-(\w+)/.exec(className || '');
  const isBlock = !inline && match;

  const copyToClipboard = () => {
    navigator.clipboard.writeText(String(children).replace(/\n$/, ''));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (isBlock) {
    return (
      <div className="relative group my-4 rounded-lg overflow-hidden border border-border/50 bg-zinc-950">
        <div className="flex items-center justify-between px-4 py-2 bg-zinc-900 border-b border-white/10">
          <span className="text-xs font-mono text-zinc-400">{match[1]}</span>
          <button
            onClick={copyToClipboard}
            className="text-zinc-400 hover:text-white transition-colors"
            title="Copy code"
          >
            {copied ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
          </button>
        </div>
        <div className="p-4 overflow-x-auto">
          <code className={cn("text-sm text-zinc-100 font-mono", className)} {...props}>
            {children}
          </code>
        </div>
      </div>
    );
  }

  return (
    <code className={cn("bg-muted/50 rounded-md px-1.5 py-0.5 text-sm font-mono text-primary", className)} {...props}>
      {children}
    </code>
  );
};

export function MessageList({ messages }: MessageListProps) {
  if (messages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
        <motion.div 
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.5 }}
          className="bg-primary/5 p-6 rounded-full mb-6 relative overflow-hidden group"
        >
          <div className="absolute inset-0 bg-primary/10 group-hover:bg-primary/20 transition-colors rounded-full animate-pulse" />
          <Bot className="h-16 w-16 text-primary relative z-10" />
        </motion.div>
        <motion.h3 
          initial={{ y: 10, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.2, duration: 0.4 }}
          className="text-xl font-medium text-foreground mb-2"
        >
          How can I help you today?
        </motion.h3>
        <motion.p 
          initial={{ y: 10, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.3, duration: 0.4 }}
          className="text-sm max-w-sm"
        >
          Engage in a conversation with your downloaded AI model.
        </motion.p>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-2">
      <AnimatePresence initial={false}>
        {messages.map((message, index) => (
          <motion.div
            key={index}
            initial={{ opacity: 0, y: 10, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className={cn(
              'flex gap-4 w-full',
              message.role === 'user' ? 'justify-end md:pl-20' : 'justify-start md:pr-20'
            )}
          >
            {message.role === 'assistant' && (
              <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center flex-shrink-0 border border-primary/20 shadow-sm mt-1">
                <Bot className="h-5 w-5 text-primary" />
              </div>
            )}
            
            <div
              className={cn(
                'rounded-2xl px-5 py-3.5 shadow-sm text-[15px] leading-relaxed',
                message.role === 'user'
                  ? 'bg-primary text-primary-foreground rounded-tr-sm'
                  : 'bg-card border border-border/50 text-foreground rounded-tl-sm w-full prose prose-sm md:prose-base prose-zinc dark:prose-invert max-w-none'
              )}
            >
              {message.role === 'user' ? (
                <p className="whitespace-pre-wrap">{message.content}</p>
              ) : (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    code: CodeBlock,
                    p: ({children}) => <p className="mb-4 last:mb-0 leading-7">{children}</p>,
                    ul: ({children}) => <ul className="list-disc pl-6 mb-4 space-y-2">{children}</ul>,
                    ol: ({children}) => <ol className="list-decimal pl-6 mb-4 space-y-2">{children}</ol>,
                    li: ({children}) => <li>{children}</li>,
                    h1: ({children}) => <h1 className="text-2xl font-semibold mb-4 mt-6 first:mt-0">{children}</h1>,
                    h2: ({children}) => <h2 className="text-xl font-semibold mb-3 mt-6 first:mt-0">{children}</h2>,
                    h3: ({children}) => <h3 className="text-lg font-semibold mb-3 mt-4 first:mt-0">{children}</h3>,
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              )}
            </div>

            {message.role === 'user' && (
              <div className="w-10 h-10 rounded-xl bg-secondary flex items-center justify-center flex-shrink-0 border border-border shadow-sm mt-1">
                <User className="h-5 w-5 text-secondary-foreground" />
              </div>
            )}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}