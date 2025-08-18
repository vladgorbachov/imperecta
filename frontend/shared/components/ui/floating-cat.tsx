import { useEffect, useRef, useState } from 'react'
import { cn } from '@/shared/utils/cn'
import { Button } from '@/shared/components/ui/button'

type Message = { role: 'user' | 'assistant'; content: string }

export default function FloatingCat() {
  const [visible, setVisible] = useState<boolean>(() => {
    const v = localStorage.getItem('catWidgetVisible')
    return v ? v === 'true' : true
  })
  const [chatOpen, setChatOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const headSize = 80
  const [pos, setPos] = useState<{ x: number; y: number }>(() => {
    const stored = localStorage.getItem('catWidgetPos')
    return stored ? JSON.parse(stored) : { x: 24, y: 24 }
  })
  const dragRef = useRef<{ dx: number; dy: number; dragging: boolean }>({ dx: 0, dy: 0, dragging: false })

  useEffect(() => {
    localStorage.setItem('catWidgetVisible', String(visible))
  }, [visible])

  useEffect(() => {
    localStorage.setItem('catWidgetPos', JSON.stringify(pos))
  }, [pos])

  const onPointerDown = (e: React.PointerEvent) => {
    dragRef.current.dragging = true
    dragRef.current.dx = e.clientX - pos.x
    dragRef.current.dy = e.clientY - pos.y
    ;(e.target as Element).setPointerCapture(e.pointerId)
  }
  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragRef.current.dragging) return
    const x = e.clientX - dragRef.current.dx
    const y = e.clientY - dragRef.current.dy
    const maxX = window.innerWidth - headSize
    const maxY = window.innerHeight - headSize
    setPos({ x: Math.max(8, Math.min(maxX, x)), y: Math.max(8, Math.min(maxY, y)) })
  }
  const onPointerUp = (e: React.PointerEvent) => {
    dragRef.current.dragging = false
    ;(e.target as Element).releasePointerCapture(e.pointerId)
  }

  const send = async () => {
    if (!input.trim()) return
    const agentId = localStorage.getItem('marketerAgentId') || ''
    if (!agentId) {
      setMessages((m) => [...m, { role: 'assistant', content: 'No agent configured. Please create Marketer in Providers.' }])
      return
    }
    const organizationId = localStorage.getItem('orgId') || '1'
    const userMsg: Message = { role: 'user', content: input }
    setMessages((m) => [...m, userMsg])
    setInput('')
    setLoading(true)
    try {
      const res = await fetch('/api/agents/marketer/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-organization-id': organizationId,
        },
        body: JSON.stringify({ message: userMsg.content, agentId, organizationId }),
      })
      const data = await res.json()
      const reply = data?.output?.reply || 'No reply'
      setMessages((m) => [...m, { role: 'assistant', content: reply }])
    } catch (e: any) {
      setMessages((m) => [...m, { role: 'assistant', content: 'Error: ' + (e.message || 'request failed') }])
    } finally {
      setLoading(false)
    }
  }

  const onTextKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!loading) send()
    }
  }

  if (!visible) {
    return (
      <button
        aria-label="Show cat"
        className="fixed bottom-4 right-4 z-[60] rounded-full px-3 py-2 bg-primary text-primary-foreground shadow-lg animate-bounce"
        onClick={() => setVisible(true)}
      >
        🐾
      </button>
    )
  }

  return (
    <div className="fixed z-[60]" style={{ left: pos.x, top: pos.y }}>
      {/* Chat box */}
      {chatOpen && (
        <div className="mb-2 w-[320px] rounded-xl border bg-background shadow-xl glass-card">
          {/* Thin header */}
          <div className="flex items-center justify-between px-3 py-1 border-b text-xs">
            <button className="text-muted-foreground hover:text-foreground" onClick={() => setChatOpen(false)}>Hide</button>
            <button className="text-muted-foreground hover:text-foreground" onClick={() => setVisible(false)}>Close</button>
          </div>
          {/* Body: big textarea (3/4 height) and a small messages strip */}
          <div className="p-3">
            <div className="relative">
              <textarea
                className="w-full h-[210px] resize-none rounded-md border bg-background p-3 pr-9 text-sm leading-5"
                placeholder="Type a message... (Enter to send, Shift+Enter for new line)"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onTextKeyDown}
              />
              {/* Tiny enter icon */}
              <div className="pointer-events-none absolute right-2 bottom-2 opacity-60 text-xs">↵</div>
            </div>
            <div className="mt-2 max-h-20 overflow-y-auto rounded-md bg-muted/20 p-2 space-y-1">
              {messages.slice(-3).map((m, i) => (
                <div key={i} className={cn('text-[12px] leading-4', m.role === 'user' ? 'text-blue-700 dark:text-blue-300' : 'text-green-700 dark:text-green-300')}>
                  <b>{m.role === 'user' ? 'You' : 'Cat'}</b>: {m.content}
                </div>
              ))}
              {messages.length === 0 && (
                <div className="text-[12px] text-muted-foreground">Ask me anything about marketing content, plans and ideas.</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Draggable Cat (drag handle only) */}
      <div
        className="relative h-20 w-20 cursor-grab active:cursor-grabbing select-none"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onDoubleClick={() => setChatOpen((v) => !v)}
        title="Double‑click to chat. Drag to move."
      >
        {/* Cat head with bigger ears */}
        <svg width="80" height="80" viewBox="0 0 80 80" className="cat-wiggle drop-shadow-lg">
          {/* ears enlarged ~30% */}
          <path d="M16 30 L30 2 L38 32 Z" fill="#222" />
          <path d="M64 30 L50 2 L42 32 Z" fill="#222" />
          {/* head */}
          <circle cx="40" cy="42" r="24" fill="#222" />
          {/* eyes */}
          <circle cx="32" cy="42" r="6" fill="#fff" />
          <circle cx="48" cy="42" r="6" fill="#fff" />
          <circle cx="33" cy="42" r="2" fill="#111" className="cat-blink" />
          <circle cx="49" cy="42" r="2" fill="#111" className="cat-blink" />
          {/* nose and smile */}
          <circle cx="40" cy="48" r="2" fill="#ffcf5b" />
          <path d="M34 52 Q40 56 46 52" stroke="#ffcf5b" strokeWidth="2" fill="none" />
          {/* whiskers */}
          <path d="M14 46 H30" stroke="#ddd" strokeWidth="2" />
          <path d="M16 50 H30" stroke="#ddd" strokeWidth="2" />
          <path d="M50 46 H66" stroke="#ddd" strokeWidth="2" />
          <path d="M50 50 H64" stroke="#ddd" strokeWidth="2" />
        </svg>
      </div>

      <div className="mt-1 flex gap-2">
        <Button size="sm" variant="secondary" onClick={() => setChatOpen((v) => !v)}>
          {chatOpen ? 'Hide chat' : 'Chat'}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setVisible(false)}>Hide</Button>
      </div>
    </div>
  )
}


