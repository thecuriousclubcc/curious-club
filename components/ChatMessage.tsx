interface Props {
  role: 'user' | 'assistant'
  content: string
}

export default function ChatMessage({ role, content }: Props) {
  const isUser = role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? 'bg-teal-700 text-white rounded-br-sm'
            : 'bg-slate-100 text-slate-800 rounded-bl-sm'
        }`}
      >
        {content}
      </div>
    </div>
  )
}
