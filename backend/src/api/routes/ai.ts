import { Router } from 'express'
import { db } from '../connection'
import { aiProviders, aiAgents, aiAgentRuns, organizations } from '../schema'
import { eq } from 'drizzle-orm'
import { encryptSecret } from '../utils/crypto'

const router = Router()

// Middleware placeholder: resolve organizationId from request (for now: from header)
router.use((req, _res, next) => {
  // In production use proper auth with Supabase and user->org mapping
  ;(req as any).organizationId = (req.headers['x-organization-id'] as string) || req.query.organizationId || req.body.organizationId
  next()
})

// Providers CRUD
router.get('/organizations/:orgId/providers', async (req, res) => {
  const orgId = req.params.orgId
  try {
    const providers = await db.select().from(aiProviders).where(eq(aiProviders.organization_id, orgId))
    res.json(providers)
  } catch (e) {
    res.status(500).json({ error: 'Failed to fetch providers' })
  }
})

router.post('/organizations/:orgId/providers', async (req, res) => {
  const orgId = req.params.orgId
  const { provider_type, base_url, app_id, flow_id, api_key, prompt_version, config } = req.body || {}
  try {
    // Ensure organization exists to satisfy FK constraint
    const existing = await db.select().from(organizations).where(eq(organizations.id, orgId))
    if (existing.length === 0) {
      await db.insert(organizations).values({ id: orgId, name: `Org ${orgId}` })
    }

    const [created] = await db.insert(aiProviders).values({
      organization_id: orgId,
      provider_type,
      base_url: (base_url || '').replace(/\/$/, ''),
      app_id,
      flow_id,
      api_key_encrypted: api_key ? encryptSecret(api_key) : null,
      prompt_version,
      config: config ? JSON.stringify(config) : null,
    }).returning()
    res.status(201).json(created)
  } catch (e) {
    const message = e instanceof Error ? e.message : 'Unknown error'
    console.error('Create provider failed:', message)
    res.status(500).json({ error: 'Failed to create provider', details: message })
  }
})

// Agents CRUD (minimal)
router.get('/organizations/:orgId/agents', async (req, res) => {
  const orgId = req.params.orgId
  try {
    const agents = await db.select().from(aiAgents).where(eq(aiAgents.organization_id, orgId))
    res.json(agents)
  } catch (e) {
    res.status(500).json({ error: 'Failed to fetch agents' })
  }
})

router.post('/organizations/:orgId/agents', async (req, res) => {
  const orgId = req.params.orgId
  const { name, type, provider_id, prompt_version, config } = req.body || {}
  try {
    const [created] = await db.insert(aiAgents).values({
      organization_id: orgId,
      name,
      type,
      provider_id,
      prompt_version,
      config: config ? JSON.stringify(config) : null,
    }).returning()
    res.status(201).json(created)
  } catch (e) {
    res.status(500).json({ error: 'Failed to create agent' })
  }
})

// Marketer chat endpoint (proxy to provider) - stub for now
router.post('/agents/marketer/chat', async (req, res) => {
  const orgId = (req as any).organizationId || req.body.organizationId
  const { message, agentId } = req.body || {}
  if (!orgId) return res.status(400).json({ error: 'organizationId required' })
  if (!message) return res.status(400).json({ error: 'message required' })
  try {
    const [agent] = await db.select().from(aiAgents).where(eq(aiAgents.id, agentId))
    if (!agent) return res.status(404).json({ error: 'Agent not found' })
    const [provider] = await db.select().from(aiProviders).where(eq(aiProviders.id, agent.provider_id!))
    if (!provider) return res.status(400).json({ error: 'Provider not configured' })

    let reply: any = null
    let usage: { promptTokens?: number; completionTokens?: number; costUsd?: number } = {}
    try {
      if (provider.provider_type === 'flowise') {
        const key = process.env.FLOWISE_API_KEY || ''
        const baseUrl = provider.base_url || process.env.FLOWISE_BASE_URL || ''
        const flowId = provider.flow_id || ''
        const resp = await fetch(`${baseUrl.replace(/\/$/, '')}/api/v1/prediction/${flowId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${key}` },
          body: JSON.stringify({ question: message, overrideConfig: { vars: { organizationId: String(orgId) } } }),
        })
        const data: any = await resp.json().catch(() => ({}))
        if (!resp.ok) throw new Error((data && data.message) || 'Flowise error')
        reply = (data && (data.text || data.answer)) || JSON.stringify(data)
      } else if (provider.provider_type === 'dify') {
        const key = process.env.DIFY_API_KEY || ''
        const baseUrl = provider.base_url || process.env.DIFY_BASE_URL || ''
        const appId = provider.app_id || process.env.DIFY_APP_ID || ''
        const resp = await fetch(`${baseUrl.replace(/\/$/, '')}/v1/apps/${appId}/run`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${key}` },
          body: JSON.stringify({ inputs: { query: message }, response_mode: 'blocking', user: String(orgId) }),
        })
        const data: any = await resp.json().catch(() => ({}))
        if (!resp.ok) throw new Error((data && data.message) || 'Dify error')
        reply = (data && (data.output || data.answer)) || JSON.stringify(data)
        const u = data && data.metadata && data.metadata.usage
        usage = { promptTokens: u?.prompt_tokens, completionTokens: u?.completion_tokens }
      }
    } catch (err: any) {
      reply = `Provider call failed: ${err.message}. Falling back to echo.`
    }

    if (reply == null) {
      reply = `Echo (mock): ${message}`
    }

    const output = { provider: provider.provider_type, reply }

    const [run] = await db.insert(aiAgentRuns).values({
      organization_id: orgId,
      agent_id: agent.id,
      status: 'succeeded',
      input: JSON.stringify({ message }),
      output: JSON.stringify(output),
      usage_prompt_tokens: usage.promptTokens ?? 0,
      usage_completion_tokens: usage.completionTokens ?? 0,
    }).returning()

    res.json({ runId: run.id, output })
  } catch (e) {
    res.status(500).json({ error: 'Failed to handle marketer chat' })
  }
})

// Unified assistant chat endpoint (uses same provider/agent under ASSISTANT type)
router.post('/assistant/chat', async (req, res) => {
  const orgId = (req as any).organizationId || req.body.organizationId
  const { message, agentId } = req.body || {}
  if (!orgId) return res.status(400).json({ error: 'organizationId required' })
  if (!message) return res.status(400).json({ error: 'message required' })
  try {
    let agentRecord = null as any
    if (agentId) {
      const [agent] = await db.select().from(aiAgents).where(eq(aiAgents.id, agentId))
      agentRecord = agent
    } else {
      const [agent] = await db.select().from(aiAgents).where(eq(aiAgents.organization_id, orgId))
      agentRecord = agent
    }
    if (!agentRecord) return res.status(404).json({ error: 'Agent not found' })
    const [provider] = await db.select().from(aiProviders).where(eq(aiProviders.id, agentRecord.provider_id!))
    if (!provider) return res.status(400).json({ error: 'Provider not configured' })

    let reply: any = null
    let usage: { promptTokens?: number; completionTokens?: number } = {}
    try {
      if (provider.provider_type === 'flowise') {
        const key = process.env.FLOWISE_API_KEY || ''
        const baseUrl = provider.base_url || process.env.FLOWISE_BASE_URL || ''
        const flowId = provider.flow_id || ''
        const resp = await fetch(`${baseUrl.replace(/\/$/, '')}/api/v1/prediction/${flowId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${key}` },
          body: JSON.stringify({ question: message, overrideConfig: { vars: { organizationId: String(orgId) } } }),
        })
        const data: any = await resp.json().catch(() => ({}))
        if (!resp.ok) throw new Error((data && data.message) || 'Flowise error')
        reply = (data && (data.text || data.answer)) || JSON.stringify(data)
      } else if (provider.provider_type === 'dify') {
        const key = process.env.DIFY_API_KEY || ''
        const baseUrl = provider.base_url || process.env.DIFY_BASE_URL || ''
        const appId = provider.app_id || process.env.DIFY_APP_ID || ''
        const resp = await fetch(`${baseUrl.replace(/\/$/, '')}/v1/apps/${appId}/run`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${key}` },
          body: JSON.stringify({ inputs: { query: message }, response_mode: 'blocking', user: String(orgId) }),
        })
        const data: any = await resp.json().catch(() => ({}))
        if (!resp.ok) throw new Error((data && data.message) || 'Dify error')
        reply = (data && (data.output || data.answer)) || JSON.stringify(data)
        const u = data && data.metadata && data.metadata.usage
        usage = { promptTokens: u?.prompt_tokens, completionTokens: u?.completion_tokens }
      }
    } catch (err: any) {
      reply = `Provider call failed: ${err.message}.`
    }

    const output = { provider: provider.provider_type, reply }
    const [run] = await db.insert(aiAgentRuns).values({
      organization_id: orgId,
      agent_id: agentRecord.id,
      status: 'succeeded',
      input: JSON.stringify({ message }),
      output: JSON.stringify(output),
      usage_prompt_tokens: usage.promptTokens ?? 0,
      usage_completion_tokens: usage.completionTokens ?? 0,
    }).returning()

    res.json({ runId: run.id, output })
  } catch {
    res.status(500).json({ error: 'Failed to handle assistant chat' })
  }
})
// DEV ONLY: quick seeding of organization, provider and marketer agent
router.post('/dev/seed-flowise', async (req, res) => {
  const { organizationId = '1', base_url, flow_id, api_key } = req.body || {}
  try {
    // ensure organization exists
    const existingOrgs = await db.select().from(organizations).where(eq(organizations.id, organizationId))
    if (existingOrgs.length === 0) {
      await db.insert(organizations).values({ id: organizationId, name: 'Default Org' })
    }

    // create provider
    const [prov] = await db.insert(aiProviders).values({
      organization_id: organizationId,
      provider_type: 'flowise',
      base_url: base_url || process.env.FLOWISE_BASE_URL || 'http://localhost:3001',
      flow_id: flow_id,
      api_key_encrypted: null, // rely on env FLOWISE_API_KEY in dev
    }).returning()

    // create marketer agent
    const [agent] = await db.insert(aiAgents).values({
      organization_id: organizationId,
      name: 'Marketer',
      type: 'MARKETER',
      provider_id: prov.id,
    }).returning()

    res.json({ organizationId, providerId: prov.id, agentId: agent.id })
  } catch (err) {
    res.status(500).json({ error: 'Failed to seed flowise', details: err instanceof Error ? err.message : String(err) })
  }
})

export default router


