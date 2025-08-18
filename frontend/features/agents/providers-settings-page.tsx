import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select'
import { withPermission } from '@/shared/hocs/with-permission'

type ProviderType = 'dify' | 'flowise'

function ProvidersSettingsPage() {
  const [organizationId, setOrganizationId] = useState('1')
  const [providerType, setProviderType] = useState<ProviderType>('dify')
  const [baseUrl, setBaseUrl] = useState('http://localhost:8000')
  const [appId, setAppId] = useState('')
  const [flowId, setFlowId] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [promptVersion, setPromptVersion] = useState('v1')
  const [createdAgentId, setCreatedAgentId] = useState<string>('')

  useEffect(() => {
    const stored = localStorage.getItem('orgId')
    if (stored) setOrganizationId(stored)
  }, [])

  const saveProvider = async () => {
    const res = await fetch(`/api/organizations/${organizationId}/providers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider_type: providerType,
        base_url: baseUrl,
        app_id: appId || null,
        flow_id: flowId || null,
        api_key: apiKey || null,
        prompt_version: promptVersion,
      }),
    })
    if (!res.ok) {
      alert('Failed to save provider')
      return
    }
    const provider = await res.json()
    const agentRes = await fetch(`/api/organizations/${organizationId}/agents`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'Marketer', type: 'MARKETER', provider_id: provider.id, prompt_version: promptVersion }),
    })
    if (agentRes.ok) {
      const agent = await agentRes.json()
      setCreatedAgentId(agent.id)
      localStorage.setItem('marketerAgentId', agent.id)
      localStorage.setItem('orgId', organizationId)
    }
    alert('Saved')
  }

  return (
    <div className="p-4">
      <Card>
        <CardHeader>
          <CardTitle>AI Providers Settings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <Input placeholder="Organization ID" value={organizationId} onChange={e => setOrganizationId(e.target.value)} />
            <Select value={providerType} onValueChange={(v: any) => setProviderType(v)}>
              <SelectTrigger>
                <SelectValue placeholder="Provider" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="dify">Dify</SelectItem>
                <SelectItem value="flowise">Flowise</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Input placeholder="Base URL" value={baseUrl} onChange={e => setBaseUrl(e.target.value)} />
          {providerType === 'dify' ? (
            <Input placeholder="Dify App ID" value={appId} onChange={e => setAppId(e.target.value)} />
          ) : (
            <Input placeholder="Flowise Flow ID" value={flowId} onChange={e => setFlowId(e.target.value)} />
          )}
          <Input placeholder="API Key (stored encrypted)" value={apiKey} onChange={e => setApiKey(e.target.value)} />
          <Input placeholder="Prompt Version" value={promptVersion} onChange={e => setPromptVersion(e.target.value)} />
          <div className="flex gap-2">
            <Button onClick={saveProvider}>Save</Button>
            {createdAgentId && <span className="text-sm">Created agent: {createdAgentId}</span>}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default withPermission('ai:providers')(ProvidersSettingsPage)


