'use client';

import { memo, useState } from 'react';
import { cn } from '@/lib/utils';
import { Message, RagSource } from '@/types';
import { User, Bot, Copy, Check, Pencil, RefreshCw, FileText, Code, Lightbulb, MessageSquare } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { motion, AnimatePresence } from 'framer-motion';
import { DocumentViewerModal } from './DocumentViewerModal';

interface MessageListProps {
  messages: Message[];
  onEditMessage?: (index: number) => void;
  onRegenerate?: () => void;
  editingIndex?: number | null;
  isLoading?: boolean;
  modelName?: string;
  /** Live tok/s while streaming; null hides the badge (show_token_speed). */
  tokenSpeed?: number | null;
  /** Show the tok/s badge at all (general.show_token_speed, default on). */
  showTokenSpeed?: boolean;
}

const CodeBlock = ({ inline, className, children }: { inline?: boolean; className?: string; children?: React.ReactNode }) => {
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
      <div className="relative group my-3 rounded-lg overflow-hidden border border-border/50 bg-zinc-950">
        <div className="flex items-center justify-between px-3 py-1.5 bg-zinc-900/80 border-b border-white/5">
          <span className="text-[11px] font-mono text-zinc-500 uppercase tracking-wider">{match[1]}</span>
          <button
            onClick={copyToClipboard}
            className="flex items-center gap-1 text-[11px] font-mono text-zinc-500 hover:text-zinc-300 transition-colors cursor-pointer"
            title="Copy code"
          >
            {copied ? <><Check className="h-3 w-3 text-green-400" /><span className="text-green-400">Copied</span></> : <><Copy className="h-3 w-3" /><span className="opacity-0 group-hover:opacity-100 transition-opacity">Copy</span></>}
          </button>
        </div>
        <div className="p-3 overflow-x-auto">
          <code className={cn("text-[13px] text-zinc-200 font-mono leading-relaxed", className)}>
            {children}
          </code>
        </div>
      </div>
    );
  }

  return (
    <code className={cn("bg-muted/50 rounded-md px-1.5 py-0.5 text-sm font-mono text-primary", className)}>
      {children}
    </code>
  );
};

const CopyMessageButton = ({ text, className }: { text: string; className?: string }) => {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={copyToClipboard}
      className={cn(
        "absolute bottom-2 right-2 p-1.5 rounded-md transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100",
        className
      )}
      title={copied ? 'Copied!' : 'Copy message'}
      aria-label="Copy message"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
};

// Memoized per-message row. Props are shallow-compared: completed messages
// keep a stable object reference (only the streaming tail is replaced in
// useChat), and onEditMessage/onRegenerate are stable callbacks — so rows stop
// re-rendering (and stop re-parsing ReactMarkdown) the moment their own state
// freezes. That turns a per-token re-render of the whole list into a re-render
// of just the last message.
const MessageItem = memo(function MessageItem({
  message,
  index,
  isEditing,
  isLast,
  isLoading,
  modelName,
  onEditMessage,
  onRegenerate,
  onViewSource,
}: {
  message: Message;
  index: number;
  isEditing: boolean;
  isLast: boolean;
  isLoading: boolean;
  modelName?: string;
  onEditMessage?: (index: number) => void;
  onRegenerate?: () => void;
  onViewSource: (source: RagSource) => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className={cn(
        'flex gap-3 md:gap-4 w-full',
        message.role === 'user' ? 'justify-end' : 'justify-start'
      )}
    >
      {message.role === 'assistant' && (
        <div className="flex flex-col items-center gap-1 flex-shrink-0 mt-1">
          <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center border border-primary/20 shadow-sm">
            <Bot className="h-5 w-5 text-primary" />
          </div>
          {(modelName || message.model) && (
            <span className="text-[9px] font-medium text-muted-foreground/60 max-w-[52px] truncate text-center leading-tight" title={message.model || modelName}>
              {message.model || modelName}
            </span>
          )}
        </div>
      )}

      <div
        className={cn(
          'rounded-2xl px-4 py-3 shadow-sm text-[15px] leading-relaxed relative group transition-shadow duration-300',
          message.role === 'user'
            ? 'bg-primary text-primary-foreground rounded-tr-sm'
            : 'bg-card border border-border/50 text-foreground rounded-tl-sm w-full prose prose-sm md:prose-base prose-zinc dark:prose-invert max-w-none',
          isEditing && message.role === 'user' &&
            'ring-2 ring-brand-accent/50 ring-offset-2 ring-offset-background shadow-md'
        )}
        // Screen readers announce the streaming reply as it grows, instead of
        // silence until the generation finishes.
        aria-live={isLoading && isLast && message.role === 'assistant' ? 'polite' : undefined}
      >
        <CopyMessageButton
          text={message.content}
          className={
            message.role === 'user'
              ? 'text-primary-foreground/70 hover:text-primary-foreground hover:bg-primary-foreground/15'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted/60'
          }
        />
        {message.role === 'user' && onEditMessage && (
          <button
            onClick={() => onEditMessage(index)}
            disabled={isLoading}
            className={cn(
              'absolute bottom-2 right-9 p-1.5 rounded-md text-primary-foreground/70 hover:text-primary-foreground hover:bg-primary-foreground/15 transition-colors disabled:opacity-0',
              isEditing
                ? 'opacity-100'
                : 'opacity-0 group-hover:opacity-100 focus:opacity-100'
            )}
            title="Edit message"
            aria-label="Edit message"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
        )}
        {message.role === 'user' ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <>
          {!message.content.trim() &&
            isLoading && isLast && (
              <p className="flex items-center gap-2 text-sm text-muted-foreground animate-pulse">
                Thinking…
              </p>
            )}
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
          </>
        )}

        {message.role === 'assistant' && message.sources && message.sources.length > 0 && (
          <div className="mt-3 pt-3 border-t border-border/60 flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Sources
            </span>
            {message.sources.map((source) => (
              <button
                key={source.filename}
                onClick={() => onViewSource(source)}
                className="inline-flex items-center gap-1 rounded-full bg-primary/10 border border-primary/20 pl-2 pr-2.5 py-0.5 text-xs text-primary hover:bg-primary/20 hover:border-primary/40 transition-colors cursor-pointer"
                title={`View ${source.filename}`}
              >
                <FileText className="h-3 w-3 shrink-0" />
                <span className="max-w-[180px] truncate font-medium">{source.filename}</span>
              </button>
            ))}
          </div>
        )}

        {message.role === 'assistant' &&
          isLast &&
          onRegenerate && (
          <button
            onClick={onRegenerate}
            disabled={isLoading}
            className="absolute bottom-2 right-9 p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors disabled:opacity-0 group-hover:opacity-100 focus:opacity-100 cursor-pointer"
            title="Regenerate response"
            aria-label="Regenerate response"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {message.role === 'user' && (
        <div className="w-10 h-10 rounded-xl bg-secondary flex items-center justify-center flex-shrink-0 border border-border shadow-sm mt-1">
          <User className="h-4 w-4 text-secondary-foreground" />
        </div>
      )}
    </motion.div>
  );
});

export function MessageList({
  messages,
  onEditMessage,
  onRegenerate,
  editingIndex,
  isLoading,
  modelName,
  tokenSpeed,
  showTokenSpeed = true,
}: MessageListProps) {
  const [viewSource, setViewSource] = useState<RagSource | null>(null);

  if (messages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground px-4">
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.4 }}
          className="bg-primary/5 p-5 rounded-2xl mb-5 border border-primary/10"
        >
          <Bot className="h-12 w-12 text-primary" />
        </motion.div>
        <motion.h3
          initial={{ y: 8, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.1, duration: 0.3 }}
          className="text-lg font-semibold text-foreground mb-1"
        >
          How can I help you today?
        </motion.h3>
        <motion.p
          initial={{ y: 8, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.15, duration: 0.3 }}
          className="text-sm mb-6"
        >
          Ask anything — or try a quick start below.
        </motion.p>
        <motion.div
          initial={{ y: 12, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.25, duration: 0.35 }}
          className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 max-w-xl w-full"
        >
          {[
            { icon: Code, label: 'Explain this code', prompt: 'Explain the following code to me in simple terms:\n```\n// paste code here\n```' },
            { icon: Lightbulb, label: 'Brainstorm ideas', prompt: 'Give me 5 creative ideas for ' },
            { icon: MessageSquare, label: 'Summarize text', prompt: 'Summarize the following in 3 bullet points:\n' },
          ].map((s) => (
            <button
              key={s.label}
              onClick={() => {
                window.dispatchEvent(new CustomEvent('chat:send', { detail: s.prompt }));
              }}
              className="flex items-start gap-2.5 p-3 rounded-xl border border-border/60 bg-card hover:bg-accent/50 hover:border-primary/30 transition-all text-left group cursor-pointer"
            >
              <div className="p-1.5 rounded-lg bg-primary/10 text-primary group-hover:bg-primary/15 transition-colors mt-0.5">
                <s.icon className="h-4 w-4" />
              </div>
              <span className="text-sm font-medium text-foreground">{s.label}</span>
            </button>
          ))}
        </motion.div>
      </div>
    );
  }

  return (
    <div className="space-y-4 pb-2">
      <DocumentViewerModal
        source={viewSource}
        open={viewSource !== null}
        onOpenChange={(open) => !open && setViewSource(null)}
      />
      <AnimatePresence initial={false}>
        {messages.map((message, index) => (
          <MessageItem
            key={index}
            message={message}
            index={index}
            isEditing={index === editingIndex}
            isLast={index === messages.length - 1}
            isLoading={!!isLoading}
            modelName={modelName}
            onEditMessage={onEditMessage}
            onRegenerate={onRegenerate}
            onViewSource={setViewSource}
          />
        ))}
      </AnimatePresence>
      {showTokenSpeed && !!tokenSpeed && (
        <div className="flex justify-center pt-1">
          <span className="text-[11px] font-mono text-muted-foreground/60">
            {tokenSpeed.toFixed(1)} tok/s
          </span>
        </div>
      )}
    </div>
  );
}
