'use client'

import { useState, useRef, useEffect } from 'react'
import { MessageCircle, X, Send, Loader2 } from 'lucide-react'
import ChatMessage from '@/components/ChatMessage'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

export default function AskWidget() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (open && messages.length === 0) {
      setMessages([
        {
          role: 'assistant',
          content:
            'こんにちは！キュリクラのAIアシスタントです。エピソードについて何でも聞いてください。例：「医療系のエピソードを教えて」「起業家のインタビューはある？」',
        },
      ])
    }
  }, [open, messages.length])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  // Suggested-question taps elsewhere on the page open the widget pre-filled
  useEffect(() => {
    function onAsk(e: Event) {
      const q = (e as CustomEvent<string>).detail
      if (typeof q === 'string' && q.trim()) {
        setOpen(true)
        setInput(q.trim())
      }
    }
    window.addEventListener('ask-widget:ask', onAsk)
    return () => window.removeEventListener('ask-widget:ask', onAsk)
  }, [])

  async function send() {
    const text = input.trim()
    if (!text || streaming) return

    const userMessage: Message = { role: 'user', content: text }
    const nextMessages = [...messages, userMessage]
    setMessages(nextMessages)
    setInput('')
    setStreaming(true)

    // Placeholder for streaming response
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }])

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: nextMessages.map((m) => ({ role: m.role, content: m.content })),
        }),
      })

      if (!res.body) throw new Error('No response body')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6).trim()
          if (payload === '[DONE]') break
          try {
            const { text } = JSON.parse(payload) as { text: string }
            setMessages((prev) => {
              const updated = [...prev]
              const last = updated[updated.length - 1]
              if (last.role === 'assistant') {
                updated[updated.length - 1] = {
                  ...last,
                  content: last.content + text,
                }
              }
              return updated
            })
          } catch {
            // ignore parse errors
          }
        }
      }
    } catch {
      setMessages((prev) => {
        const updated = [...prev]
        const last = updated[updated.length - 1]
        if (last.role === 'assistant' && last.content === '') {
          updated[updated.length - 1] = {
            role: 'assistant',
            content: '申し訳ありません、エラーが発生しました。もう一度お試しください。',
          }
        }
        return updated
      })
    } finally {
      setStreaming(false)
    }
  }

  return (
    <>
      {/* Floating button */}
      <button
        onClick={() => setOpen(true)}
        className={`fixed bottom-6 right-6 z-40 w-14 h-14 rounded-full bg-teal-700 text-white shadow-lg hover:bg-teal-800 transition-all flex items-center justify-center ${open ? 'scale-0 opacity-0' : 'scale-100 opacity-100'}`}
        aria-label="Ask the Club"
      >
        <MessageCircle size={22} />
      </button>

      {/* Drawer */}
      {open && (
        <div className="fixed bottom-6 right-6 z-50 w-[350px] max-w-[calc(100vw-24px)] flex flex-col rounded-2xl shadow-2xl bg-white border border-slate-100 overflow-hidden"
          style={{ height: 'min(520px, calc(100vh - 48px))' }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-teal-700 text-white">
            <div>
              <p className="text-sm font-semibold">Ask the Club</p>
              <p className="text-xs text-teal-200">エピソードについてAIが答えます</p>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="text-teal-200 hover:text-white transition-colors"
            >
              <X size={18} />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
            {messages.map((msg, i) => (
              <ChatMessage key={i} role={msg.role} content={msg.content} />
            ))}
            {streaming && messages[messages.length - 1]?.content === '' && (
              <div className="flex justify-start">
                <div className="bg-slate-100 rounded-2xl rounded-bl-sm px-4 py-3">
                  <Loader2 size={14} className="text-teal-600 animate-spin" />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="px-4 py-3 border-t border-slate-100 flex items-center gap-2">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && send()}
              placeholder="エピソードについて質問…"
              disabled={streaming}
              className="flex-1 text-sm px-3 py-2 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent placeholder:text-slate-400 disabled:opacity-50"
            />
            <button
              onClick={send}
              disabled={streaming || !input.trim()}
              className="w-9 h-9 rounded-xl bg-teal-700 text-white flex items-center justify-center hover:bg-teal-800 transition-colors disabled:opacity-40"
            >
              <Send size={14} />
            </button>
          </div>
        </div>
      )}
    </>
  )
}
