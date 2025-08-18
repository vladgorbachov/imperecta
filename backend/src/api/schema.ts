import { pgTable, text, timestamp, boolean, varchar, integer, numeric } from 'drizzle-orm/pg-core'
import { createId } from '@paralleldrive/cuid2'

// Users table
export const users = pgTable('users', {
  id: text('id').primaryKey().$defaultFn(() => createId()),
  supabase_user_id: text('supabase_user_id').unique().notNull(),
  first_name: varchar('first_name', { length: 100 }).notNull(),
  last_name: varchar('last_name', { length: 100 }).notNull(),
  middle_name: varchar('middle_name', { length: 100 }),
  email: varchar('email', { length: 255 }).unique().notNull(),
  phone: varchar('phone', { length: 20 }),
  avatar_url: text('avatar_url'),
  created_at: timestamp('created_at').defaultNow().notNull(),
  updated_at: timestamp('updated_at').defaultNow().notNull(),
})

// User settings table
export const userSettings = pgTable('user_settings', {
  id: text('id').primaryKey().$defaultFn(() => createId()),
  user_id: text('user_id').references(() => users.id, { onDelete: 'cascade' }).notNull(),
  theme: varchar('theme', { length: 20 }).default('system').notNull(),
  language: varchar('language', { length: 10 }).default('en').notNull(),
  notifications_email: boolean('notifications_email').default(true).notNull(),
  notifications_push: boolean('notifications_push').default(true).notNull(),
  notifications_sms: boolean('notifications_sms').default(false).notNull(),
  privacy_profile_visible: boolean('privacy_profile_visible').default(true).notNull(),
  privacy_activity_visible: boolean('privacy_activity_visible').default(true).notNull(),
  created_at: timestamp('created_at').defaultNow().notNull(),
  updated_at: timestamp('updated_at').defaultNow().notNull(),
})

// Organizations table
export const organizations = pgTable('organizations', {
  id: text('id').primaryKey().$defaultFn(() => createId()),
  name: varchar('name', { length: 255 }).notNull(),
  description: text('description'),
  logo_url: text('logo_url'),
  website: varchar('website', { length: 255 }),
  created_at: timestamp('created_at').defaultNow().notNull(),
  updated_at: timestamp('updated_at').defaultNow().notNull(),
})

// Organization members table
export const organizationMembers = pgTable('organization_members', {
  id: text('id').primaryKey().$defaultFn(() => createId()),
  organization_id: text('organization_id').references(() => organizations.id, { onDelete: 'cascade' }).notNull(),
  user_id: text('user_id').references(() => users.id, { onDelete: 'cascade' }).notNull(),
  role: varchar('role', { length: 50 }).default('member').notNull(),
  permissions: text('permissions'), // JSON string
  created_at: timestamp('created_at').defaultNow().notNull(),
  updated_at: timestamp('updated_at').defaultNow().notNull(),
})

// Projects table
export const projects = pgTable('projects', {
  id: text('id').primaryKey().$defaultFn(() => createId()),
  organization_id: text('organization_id').references(() => organizations.id, { onDelete: 'cascade' }).notNull(),
  name: varchar('name', { length: 255 }).notNull(),
  description: text('description'),
  status: varchar('status', { length: 50 }).default('active').notNull(),
  priority: varchar('priority', { length: 20 }).default('medium').notNull(),
  start_date: timestamp('start_date'),
  end_date: timestamp('end_date'),
  created_at: timestamp('created_at').defaultNow().notNull(),
  updated_at: timestamp('updated_at').defaultNow().notNull(),
})

// Tasks table
export const tasks = pgTable('tasks', {
  id: text('id').primaryKey().$defaultFn(() => createId()),
  project_id: text('project_id').references(() => projects.id, { onDelete: 'cascade' }).notNull(),
  assigned_to: text('assigned_to').references(() => users.id, { onDelete: 'set null' }),
  created_by: text('created_by').references(() => users.id, { onDelete: 'cascade' }).notNull(),
  title: varchar('title', { length: 255 }).notNull(),
  description: text('description'),
  status: varchar('status', { length: 50 }).default('todo').notNull(),
  priority: varchar('priority', { length: 20 }).default('medium').notNull(),
  due_date: timestamp('due_date'),
  completed_at: timestamp('completed_at'),
  created_at: timestamp('created_at').defaultNow().notNull(),
  updated_at: timestamp('updated_at').defaultNow().notNull(),
})

// Task comments table
export const taskComments = pgTable('task_comments', {
  id: text('id').primaryKey().$defaultFn(() => createId()),
  task_id: text('task_id').references(() => tasks.id, { onDelete: 'cascade' }).notNull(),
  user_id: text('user_id').references(() => users.id, { onDelete: 'cascade' }).notNull(),
  content: text('content').notNull(),
  created_at: timestamp('created_at').defaultNow().notNull(),
  updated_at: timestamp('updated_at').defaultNow().notNull(),
})

// Task attachments table
export const taskAttachments = pgTable('task_attachments', {
  id: text('id').primaryKey().$defaultFn(() => createId()),
  task_id: text('task_id').references(() => tasks.id, { onDelete: 'cascade' }).notNull(),
  user_id: text('user_id').references(() => users.id, { onDelete: 'cascade' }).notNull(),
  filename: varchar('filename', { length: 255 }).notNull(),
  file_url: text('file_url').notNull(),
  file_size: integer('file_size'),
  mime_type: varchar('mime_type', { length: 100 }),
  created_at: timestamp('created_at').defaultNow().notNull(),
})

// Activity logs table
export const activityLogs = pgTable('activity_logs', {
  id: text('id').primaryKey().$defaultFn(() => createId()),
  user_id: text('user_id').references(() => users.id, { onDelete: 'cascade' }).notNull(),
  organization_id: text('organization_id').references(() => organizations.id, { onDelete: 'cascade' }),
  project_id: text('project_id').references(() => projects.id, { onDelete: 'cascade' }),
  task_id: text('task_id').references(() => tasks.id, { onDelete: 'cascade' }),
  action: varchar('action', { length: 100 }).notNull(),
  entity_type: varchar('entity_type', { length: 50 }).notNull(),
  entity_id: text('entity_id'),
  details: text('details'), // JSON string
  created_at: timestamp('created_at').defaultNow().notNull(),
}) 

// AI providers per organization (Dify / Flowise / SuperAGI)
export const aiProviders = pgTable('ai_providers', {
  id: text('id').primaryKey().$defaultFn(() => createId()),
  organization_id: text('organization_id').references(() => organizations.id, { onDelete: 'cascade' }).notNull(),
  provider_type: varchar('provider_type', { length: 50 }).notNull(), // 'dify' | 'flowise' | 'superagi'
  base_url: text('base_url').notNull(),
  app_id: text('app_id'), // Dify app id
  flow_id: text('flow_id'), // Flowise flow id
  auth_type: varchar('auth_type', { length: 50 }).default('apiKey').notNull(),
  api_key_encrypted: text('api_key_encrypted'),
  prompt_version: varchar('prompt_version', { length: 50 }),
  config: text('config'), // JSON string
  created_at: timestamp('created_at').defaultNow().notNull(),
  updated_at: timestamp('updated_at').defaultNow().notNull(),
})

// AI agents per organization (Marketer / Accountant / Sales)
export const aiAgents = pgTable('ai_agents', {
  id: text('id').primaryKey().$defaultFn(() => createId()),
  organization_id: text('organization_id').references(() => organizations.id, { onDelete: 'cascade' }).notNull(),
  name: varchar('name', { length: 255 }).notNull(),
  type: varchar('type', { length: 50 }).notNull(), // 'MARKETER' | 'ACCOUNTANT' | 'SALES'
  provider_id: text('provider_id').references(() => aiProviders.id, { onDelete: 'set null' }),
  is_enabled: boolean('is_enabled').default(true).notNull(),
  prompt_version: varchar('prompt_version', { length: 50 }),
  config: text('config'), // JSON string
  created_at: timestamp('created_at').defaultNow().notNull(),
  updated_at: timestamp('updated_at').defaultNow().notNull(),
})

// AI agent run history and usage
export const aiAgentRuns = pgTable('ai_agent_runs', {
  id: text('id').primaryKey().$defaultFn(() => createId()),
  organization_id: text('organization_id').references(() => organizations.id, { onDelete: 'cascade' }).notNull(),
  agent_id: text('agent_id').references(() => aiAgents.id, { onDelete: 'cascade' }).notNull(),
  user_id: text('user_id').references(() => users.id, { onDelete: 'set null' }),
  status: varchar('status', { length: 50 }).default('running').notNull(), // running | succeeded | failed
  input: text('input'), // JSON string
  output: text('output'), // JSON string
  usage_prompt_tokens: integer('usage_prompt_tokens'),
  usage_completion_tokens: integer('usage_completion_tokens'),
  cost_usd: numeric('cost_usd', { precision: 12, scale: 6 }),
  error: text('error'),
  created_at: timestamp('created_at').defaultNow().notNull(),
  updated_at: timestamp('updated_at').defaultNow().notNull(),
})

// Audit logs (security-relevant actions)
export const auditLogs = pgTable('audit_logs', {
  id: text('id').primaryKey().$defaultFn(() => createId()),
  organization_id: text('organization_id').references(() => organizations.id, { onDelete: 'cascade' }).notNull(),
  user_id: text('user_id').references(() => users.id, { onDelete: 'set null' }),
  action: varchar('action', { length: 100 }).notNull(),
  metadata: text('metadata'), // JSON string
  created_at: timestamp('created_at').defaultNow().notNull(),
})

// Encrypted secrets per organization (GA, social, etc.)
export const secrets = pgTable('secrets', {
  id: text('id').primaryKey().$defaultFn(() => createId()),
  organization_id: text('organization_id').references(() => organizations.id, { onDelete: 'cascade' }).notNull(),
  key: varchar('key', { length: 255 }).notNull(),
  value_encrypted: text('value_encrypted').notNull(),
  created_at: timestamp('created_at').defaultNow().notNull(),
  updated_at: timestamp('updated_at').defaultNow().notNull(),
})

// Knowledge documents for RAG per organization
export const aiDocuments = pgTable('ai_documents', {
  id: text('id').primaryKey().$defaultFn(() => createId()),
  organization_id: text('organization_id').references(() => organizations.id, { onDelete: 'cascade' }).notNull(),
  source: varchar('source', { length: 50 }).notNull(), // upload | url | other
  uri: text('uri').notNull(),
  index_namespace: varchar('index_namespace', { length: 255 }),
  metadata: text('metadata'), // JSON string
  created_at: timestamp('created_at').defaultNow().notNull(),
})