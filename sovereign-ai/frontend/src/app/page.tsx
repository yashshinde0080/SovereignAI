'use client'

import { useState } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Send, TerminalSquare, Loader2 } from 'lucide-react'
import { useStore } from '@/store/useStore'
import { Badge } from '@/components/ui/badge'

export default function ChatConsole() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<{role: string, content: string}[]>([])
  const { currentModel, currentMode, status } = useStore()

  const handleSend = async () => {
    if (!input.trim()) return

    const newMessages = [...messages, { role: 'user', content: input }]
    setMessages(newMessages)
    setInput('')

    // Create a placeholder for the assistant response
    const assistantMessageIndex = newMessages.length
    setMessages([...newMessages, { role: 'assistant', content: '' }])

    try {
      const res = await fetch('http://127.0.0.1:8000/v1/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: currentModel,
          messages: newMessages,
          mode: currentMode,
          stream: true
        })
      })

      if (!res.body) throw new Error('No body in response')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()

      let finalContent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n').filter(Boolean)

        for (const line of lines) {
          try {
            const data = JSON.parse(line)
            finalContent += data.token
            setMessages(prev => {
              const updated = [...prev]
              updated[assistantMessageIndex].content = finalContent
              return updated
            })
          } catch (e) {
            console.error('Failed to parse streaming line:', line, e)
          }
        }
      }
    } catch (err) {
      console.error(err)
      setMessages(prev => {
        const updated = [...prev]
        updated[assistantMessageIndex].content = 'Error: Failed to fetch response.'
        return updated
      })
    }
  }

  return (
    <div className="flex flex-col h-full space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white flex items-center">
            <TerminalSquare className="mr-2" />
            Compute Console
          </h2>
          <p className="text-sm text-slate-400">Interactive execution environment for {currentModel}.</p>
        </div>
        <div className="flex space-x-2">
           <Badge variant="outline" className="font-mono bg-slate-800 text-blue-400 border-blue-900">
             ENV: AIR-GAPPED
           </Badge>
        </div>
      </div>

      <Card className="flex-1 flex flex-col border-slate-800 bg-slate-900 overflow-hidden shadow-xl rounded-xl">
        <ScrollArea className="flex-1 p-4 overflow-y-auto">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-500 font-mono space-y-4">
              <TerminalSquare className="h-12 w-12 opacity-50 mb-2" />
              <p>System Ready. Engine loaded in {currentMode.toUpperCase()} mode.</p>
              <p className="text-xs max-w-sm text-center">Execute commands or query the model. Data never leaves this machine.</p>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[80%] rounded-lg p-4 font-mono text-sm shadow-md ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-800 border border-slate-700 text-slate-300'
                  }`}>
                    {msg.content || (
                      <span className="flex items-center text-slate-500">
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Computing...
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>

        <div className="p-4 bg-slate-950 border-t border-slate-800 mt-auto">
          <div className="flex gap-2">
            <Textarea
              placeholder="Enter instruction..."
              className="resize-none bg-slate-900 border-slate-700 text-slate-200 font-mono min-h-[60px]"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
            />
            <Button
              onClick={handleSend}
              disabled={status === 'generating' || !input.trim()}
              className="bg-blue-600 hover:bg-blue-700 text-white h-auto"
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
          <div className="text-xs text-slate-500 mt-2 font-mono flex justify-between">
            <span>Shift+Enter for newline</span>
            <span>Local inference. Zero telemetry.</span>
          </div>
        </div>
      </Card>
    </div>
  )
}
