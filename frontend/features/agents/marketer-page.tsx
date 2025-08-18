import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Textarea } from '@/shared/components/ui/textarea'

import { withPermission } from '@/shared/hocs/with-permission'

function MarketerPage() {
  const [organizationId, setOrganizationId] = useState('1')
  const [agentId, setAgentId] = useState<string>('')
  const [message, setMessage] = useState('Сгенерируй идеи постов для соцсетей на следующую неделю')
  const [history, setHistory] = useState<Array<{ role: 'user' | 'assistant'; content: string }>>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const stored = localStorage.getItem('orgId')
    if (stored) setOrganizationId(stored)
  }, [])

  const send = async () => {
    if (!agentId) {
      alert('Создайте и выберите агента в настройках провайдеров')
      return
    }
    setLoading(true)
    setHistory(h => [...h, { role: 'user', content: message }])
    try {
      const res = await fetch('/api/agents/marketer/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-organization-id': organizationId,
        },
        body: JSON.stringify({ message, agentId, organizationId }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Request failed')
      setHistory(h => [...h, { role: 'assistant', content: data.output?.reply ?? 'No reply' }])
      setMessage('')
    } catch (e: any) {
      setHistory(h => [...h, { role: 'assistant', content: 'Error: ' + e.message }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-4 space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>AI Marketer</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <Input placeholder="Organization ID" value={organizationId} onChange={e => setOrganizationId(e.target.value)} />
            <Input placeholder="Agent ID" value={agentId} onChange={e => setAgentId(e.target.value)} />
          </div>
          <Textarea rows={4} placeholder="Введите запрос" value={message} onChange={e => setMessage(e.target.value)} />
          <div className="flex gap-2">
            <Button onClick={send} disabled={loading}>{loading ? 'Sending...' : 'Send'}</Button>
            <Button variant="secondary" onClick={() => setMessage('Сделай контент-план на месяц')}>
              Быстрая задача: Контент-план
            </Button>
          </div>
          <div className="space-y-2">
            {history.map((m, i) => (
              <div key={i} className={m.role === 'user' ? 'text-blue-700' : 'text-green-700'}>
                <b>{m.role === 'user' ? 'Вы' : 'Агент'}:</b> {m.content}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default withPermission('ai:agents:marketer')(MarketerPage)


