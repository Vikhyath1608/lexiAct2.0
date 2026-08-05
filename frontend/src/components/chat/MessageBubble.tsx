// src/components/chat/MessageBubble.tsx
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Message } from '@/types'
import { format } from 'date-fns'
import { Zap } from 'lucide-react'
import clsx from 'clsx'

export default function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  return (
    <div className={clsx('flex gap-2.5 items-end animate-fade-up', isUser && 'flex-row-reverse')}>
      <div className={clsx('w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold',
        isUser ? 'bg-gradient-to-br from-primary to-accent text-white' : 'bg-white/10 text-white/60')}>
        {isUser ? 'U' : 'L'}
      </div>
      <div className={clsx('max-w-[72%] flex flex-col gap-1', isUser && 'items-end')}>
        {message.automationType && (
          <div className="flex items-center gap-1 text-[10px] text-primary-light bg-primary/10 border border-primary/20 rounded-full px-2 py-0.5 w-fit">
            <Zap size={9} />{message.automationType}
          </div>
        )}
        <div className={clsx('rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
          isUser ? 'bg-gradient-to-br from-primary to-accent text-white rounded-br-sm'
                 : 'glass rounded-bl-sm text-slate-200')}>
          {isUser ? <p className="whitespace-pre-wrap">{message.content}</p> : (
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
              code({ className, children }) {
                return className?.includes('language-')
                  ? <pre className="bg-black/30 rounded-lg p-3 overflow-x-auto text-xs my-2"><code>{children}</code></pre>
                  : <code className="bg-black/30 px-1.5 py-0.5 rounded text-xs font-mono">{children}</code>
              },
              a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer" className="text-accent-light underline">{children}</a>,
              ul: ({ children }) => <ul className="list-disc list-inside space-y-1 my-1">{children}</ul>,
              ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 my-1">{children}</ol>,
              strong: ({ children }) => <strong className="font-bold text-white">{children}</strong>,
            }}>
              {message.content}
            </ReactMarkdown>
          )}
        </div>
        <p className="text-[10px] text-white/20 px-1">{format(message.createdAt, 'HH:mm')}</p>
      </div>
    </div>
  )
}
