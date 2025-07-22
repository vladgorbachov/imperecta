import { pgTable, uuid, varchar, text, timestamp, index } from 'drizzle-orm/pg-core'
import { relations } from 'drizzle-orm'

// Users table
export const users = pgTable('users', {
  id: uuid('id').primaryKey().defaultRandom(),
  supabase_user_id: uuid('supabase_user_id').unique().notNull(),
  first_name: varchar('first_name', { length: 50 }).notNull(),
  last_name: varchar('last_name', { length: 50 }).notNull(),
  middle_name: varchar('middle_name', { length: 50 }),
  email: varchar('email', { length: 255 }).unique().notNull(),
  phone: varchar('phone', { length: 20 }),
  avatar_url: text('avatar_url'),
  created_at: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updated_at: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
}, (table) => ({
  emailIdx: index('idx_users_email').on(table.email),
  supabaseUserIdIdx: index('idx_users_supabase_user_id').on(table.supabase_user_id),
}))

// Projects table
export const projects = pgTable('projects', {
  id: uuid('id').primaryKey().defaultRandom(),
  name: varchar('name', { length: 255 }).notNull(),
  description: text('description').notNull(),
  status: varchar('status', { length: 20 }).notNull().default('active'), // 'active' | 'completed' | 'on-hold' | 'cancelled'
  priority: varchar('priority', { length: 20 }).notNull().default('medium'), // 'low' | 'medium' | 'high' | 'urgent'
  start_date: timestamp('start_date', { withTimezone: true }).notNull(),
  end_date: timestamp('end_date', { withTimezone: true }),
  budget: varchar('budget', { length: 20 }),
  created_by: uuid('created_by').notNull().references(() => users.id),
  created_at: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updated_at: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
})

// Tasks table
export const tasks = pgTable('tasks', {
  id: uuid('id').primaryKey().defaultRandom(),
  title: varchar('title', { length: 255 }).notNull(),
  description: text('description').notNull(),
  status: varchar('status', { length: 20 }).notNull().default('todo'), // 'todo' | 'in-progress' | 'review' | 'completed'
  priority: varchar('priority', { length: 20 }).notNull().default('medium'), // 'low' | 'medium' | 'high' | 'urgent'
  project_id: uuid('project_id').notNull().references(() => projects.id),
  assigned_to: uuid('assigned_to').notNull().references(() => users.id),
  created_by: uuid('created_by').notNull().references(() => users.id),
  due_date: timestamp('due_date', { withTimezone: true }),
  completed_at: timestamp('completed_at', { withTimezone: true }),
  created_at: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updated_at: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
})

// Clients table
export const clients = pgTable('clients', {
  id: uuid('id').primaryKey().defaultRandom(),
  name: varchar('name', { length: 255 }).notNull(),
  email: varchar('email', { length: 255 }).notNull(),
  phone: varchar('phone', { length: 20 }),
  company: varchar('company', { length: 255 }),
  address: text('address'),
  notes: text('notes'),
  created_by: uuid('created_by').notNull().references(() => users.id),
  created_at: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updated_at: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
})

// Team members table
export const teamMembers = pgTable('team_members', {
  id: uuid('id').primaryKey().defaultRandom(),
  user_id: uuid('user_id').notNull().references(() => users.id),
  role: varchar('role', { length: 20 }).notNull().default('member'), // 'admin' | 'manager' | 'member' | 'viewer'
  department: varchar('department', { length: 100 }),
  position: varchar('position', { length: 100 }),
  joined_at: timestamp('joined_at', { withTimezone: true }).defaultNow().notNull(),
  created_at: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updated_at: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
})

// Documents table
export const documents = pgTable('documents', {
  id: uuid('id').primaryKey().defaultRandom(),
  title: varchar('title', { length: 255 }).notNull(),
  description: text('description'),
  file_url: text('file_url').notNull(),
  file_type: varchar('file_type', { length: 50 }).notNull(),
  file_size: varchar('file_size', { length: 20 }).notNull(),
  uploaded_by: uuid('uploaded_by').notNull().references(() => users.id),
  project_id: uuid('project_id').references(() => projects.id),
  is_public: varchar('is_public', { length: 5 }).notNull().default('false'), // 'true' | 'false'
  created_at: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updated_at: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
})

// Invoices table
export const invoices = pgTable('invoices', {
  id: uuid('id').primaryKey().defaultRandom(),
  invoice_number: varchar('invoice_number', { length: 50 }).notNull(),
  client_id: uuid('client_id').notNull().references(() => clients.id),
  project_id: uuid('project_id').references(() => projects.id),
  amount: varchar('amount', { length: 20 }).notNull(),
  currency: varchar('currency', { length: 10 }).notNull().default('USD'),
  status: varchar('status', { length: 20 }).notNull().default('draft'), // 'draft' | 'sent' | 'paid' | 'overdue' | 'cancelled'
  issue_date: timestamp('issue_date', { withTimezone: true }).notNull(),
  due_date: timestamp('due_date', { withTimezone: true }).notNull(),
  paid_date: timestamp('paid_date', { withTimezone: true }),
  notes: text('notes'),
  created_by: uuid('created_by').notNull().references(() => users.id),
  created_at: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updated_at: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
})

// User settings table
export const userSettings = pgTable('user_settings', {
  id: uuid('id').primaryKey().defaultRandom(),
  user_id: uuid('user_id').unique().notNull().references(() => users.id),
  theme: varchar('theme', { length: 10 }).notNull().default('system'), // 'light' | 'dark' | 'system'
  language: varchar('language', { length: 5 }).notNull().default('en'), // 'en' | 'ru'
  notifications_email: varchar('notifications_email', { length: 5 }).notNull().default('true'), // 'true' | 'false'
  notifications_push: varchar('notifications_push', { length: 5 }).notNull().default('true'), // 'true' | 'false'
  notifications_sms: varchar('notifications_sms', { length: 5 }).notNull().default('false'), // 'true' | 'false'
  privacy_profile_visible: varchar('privacy_profile_visible', { length: 5 }).notNull().default('true'), // 'true' | 'false'
  privacy_activity_visible: varchar('privacy_activity_visible', { length: 5 }).notNull().default('true'), // 'true' | 'false'
  created_at: timestamp('created_at', { withTimezone: true }).defaultNow().notNull(),
  updated_at: timestamp('updated_at', { withTimezone: true }).defaultNow().notNull(),
})

// Relations
export const usersRelations = relations(users, ({ many, one }) => ({
  projects: many(projects),
  tasks: many(tasks),
  clients: many(clients),
  teamMembers: many(teamMembers),
  documents: many(documents),
  invoices: many(invoices),
  settings: one(userSettings),
}))

export const projectsRelations = relations(projects, ({ one, many }) => ({
  createdBy: one(users, {
    fields: [projects.created_by],
    references: [users.id],
  }),
  tasks: many(tasks),
  documents: many(documents),
  invoices: many(invoices),
}))

export const tasksRelations = relations(tasks, ({ one }) => ({
  project: one(projects, {
    fields: [tasks.project_id],
    references: [projects.id],
  }),
  assignedTo: one(users, {
    fields: [tasks.assigned_to],
    references: [users.id],
  }),
  createdBy: one(users, {
    fields: [tasks.created_by],
    references: [users.id],
  }),
}))

export const clientsRelations = relations(clients, ({ one, many }) => ({
  createdBy: one(users, {
    fields: [clients.created_by],
    references: [users.id],
  }),
  invoices: many(invoices),
}))

export const teamMembersRelations = relations(teamMembers, ({ one }) => ({
  user: one(users, {
    fields: [teamMembers.user_id],
    references: [users.id],
  }),
}))

export const documentsRelations = relations(documents, ({ one }) => ({
  uploadedBy: one(users, {
    fields: [documents.uploaded_by],
    references: [users.id],
  }),
  project: one(projects, {
    fields: [documents.project_id],
    references: [projects.id],
  }),
}))

export const invoicesRelations = relations(invoices, ({ one }) => ({
  client: one(clients, {
    fields: [invoices.client_id],
    references: [clients.id],
  }),
  project: one(projects, {
    fields: [invoices.project_id],
    references: [projects.id],
  }),
  createdBy: one(users, {
    fields: [invoices.created_by],
    references: [users.id],
  }),
}))

export const userSettingsRelations = relations(userSettings, ({ one }) => ({
  user: one(users, {
    fields: [userSettings.user_id],
    references: [users.id],
  }),
})) 