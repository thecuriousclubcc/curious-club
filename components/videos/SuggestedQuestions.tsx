'use client'

import { MessageCircle } from 'lucide-react'

interface Props {
  questions: string[]
}

// Tapping a question opens the AskWidget pre-filled with it
export default function SuggestedQuestions({ questions }: Props) {
  if (questions.length === 0) return null

  return (
    <div className="pt-2">
      <p className="text-xs font-medium text-slate-500 mb-3">
        この動画を見たら考えたいこと（タップしてAIに聞く）
      </p>
      <ul className="space-y-2">
        {questions.map((q, i) => (
          <li key={i}>
            <button
              onClick={() =>
                window.dispatchEvent(new CustomEvent('ask-widget:ask', { detail: q }))
              }
              className="group flex items-start gap-2 text-left text-sm text-slate-600 hover:text-teal-700 transition-colors"
            >
              <span className="text-teal-500 mt-0.5 shrink-0">Q.</span>
              <span className="underline-offset-4 group-hover:underline">{q}</span>
              <MessageCircle
                size={13}
                className="mt-1 shrink-0 text-slate-300 group-hover:text-teal-500 transition-colors"
              />
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
