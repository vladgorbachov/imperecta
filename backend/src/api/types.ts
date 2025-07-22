// Supabase types
export interface SupabaseUser {
  id: string
  email: string
  user_metadata: {
    full_name?: string
    avatar_url?: string
  }
  created_at: string
  updated_at: string
}

// Database User types
export interface DatabaseUser {
  id: string
  supabase_user_id: string
  first_name: string
  last_name: string
  middle_name?: string
  email: string
  phone?: string
  avatar_url?: string
  created_at: string
  updated_at: string
}

export interface CreateUserRequest {
  supabase_user_id: string
  first_name: string
  last_name: string
  middle_name?: string
  email: string
  phone?: string
}

export interface UpdateUserRequest {
  first_name?: string
  last_name?: string
  middle_name?: string
  phone?: string
  avatar_url?: string
}

// API Response types
export interface ApiResponse<T> {
  data: T | null
  error: string | null
  success: boolean
}

// Auth types
export interface LoginRequest {
  email: string
  password: string
}

export interface SignUpRequest {
  email: string
  password: string
  first_name: string
  last_name: string
  middle_name?: string
  phone?: string
}

export interface ResetPasswordRequest {
  email: string
}

// Project types
export interface Project {
  id: string
  name: string
  description: string
  status: 'active' | 'completed' | 'on-hold' | 'cancelled'
  priority: 'low' | 'medium' | 'high' | 'urgent'
  start_date: string
  end_date?: string
  budget?: string
  created_by: string
  assigned_to?: string[]
  created_at: string
  updated_at: string
}

export interface CreateProjectRequest {
  name: string
  description: string
  status: 'active' | 'completed' | 'on-hold' | 'cancelled'
  priority: 'low' | 'medium' | 'high' | 'urgent'
  start_date: string
  end_date?: string
  budget?: string
  assigned_to?: string[]
}

export interface UpdateProjectRequest {
  name?: string
  description?: string
  status?: 'active' | 'completed' | 'on-hold' | 'cancelled'
  priority?: 'low' | 'medium' | 'high' | 'urgent'
  start_date?: string
  end_date?: string
  budget?: string
  assigned_to?: string[]
}

// Task types
export interface Task {
  id: string
  title: string
  description: string
  status: 'todo' | 'in-progress' | 'review' | 'completed'
  priority: 'low' | 'medium' | 'high' | 'urgent'
  project_id: string
  assigned_to: string
  created_by: string
  due_date?: string
  completed_at?: string
  created_at: string
  updated_at: string
}

export interface CreateTaskRequest {
  title: string
  description: string
  status: 'todo' | 'in-progress' | 'review' | 'completed'
  priority: 'low' | 'medium' | 'high' | 'urgent'
  project_id: string
  assigned_to: string
  due_date?: string
}

export interface UpdateTaskRequest {
  title?: string
  description?: string
  status?: 'todo' | 'in-progress' | 'review' | 'completed'
  priority?: 'low' | 'medium' | 'high' | 'urgent'
  assigned_to?: string
  due_date?: string
  completed_at?: string
}

// Client types
export interface Client {
  id: string
  name: string
  email: string
  phone?: string
  company?: string
  address?: string
  notes?: string
  created_by: string
  created_at: string
  updated_at: string
}

export interface CreateClientRequest {
  name: string
  email: string
  phone?: string
  company?: string
  address?: string
  notes?: string
}

export interface UpdateClientRequest {
  name?: string
  email?: string
  phone?: string
  company?: string
  address?: string
  notes?: string
}

// Team types
export interface TeamMember {
  id: string
  user_id: string
  role: 'admin' | 'manager' | 'member' | 'viewer'
  department?: string
  position?: string
  joined_at: string
  created_at: string
  updated_at: string
  user: DatabaseUser
}

export interface CreateTeamMemberRequest {
  user_id: string
  role: 'admin' | 'manager' | 'member' | 'viewer'
  department?: string
  position?: string
}

export interface UpdateTeamMemberRequest {
  role?: 'admin' | 'manager' | 'member' | 'viewer'
  department?: string
  position?: string
}

// Document types
export interface Document {
  id: string
  title: string
  description?: string
  file_url: string
  file_type: string
  file_size: number
  uploaded_by: string
  project_id?: string
  is_public: boolean
  created_at: string
  updated_at: string
}

export interface CreateDocumentRequest {
  title: string
  description?: string
  file_url: string
  file_type: string
  file_size: number
  project_id?: string
  is_public: boolean
}

export interface UpdateDocumentRequest {
  title?: string
  description?: string
  is_public?: boolean
}

// Finance types
export interface Invoice {
  id: string
  invoice_number: string
  client_id: string
  project_id?: string
  amount: number
  currency: string
  status: 'draft' | 'sent' | 'paid' | 'overdue' | 'cancelled'
  issue_date: string
  due_date: string
  paid_date?: string
  notes?: string
  created_by: string
  created_at: string
  updated_at: string
}

export interface CreateInvoiceRequest {
  invoice_number: string
  client_id: string
  project_id?: string
  amount: number
  currency: string
  status: 'draft' | 'sent' | 'paid' | 'overdue' | 'cancelled'
  issue_date: string
  due_date: string
  notes?: string
}

export interface UpdateInvoiceRequest {
  invoice_number?: string
  client_id?: string
  project_id?: string
  amount?: number
  currency?: string
  status?: 'draft' | 'sent' | 'paid' | 'overdue' | 'cancelled'
  issue_date?: string
  due_date?: string
  paid_date?: string
  notes?: string
}

// Analytics types
export interface AnalyticsData {
  total_projects: number
  active_projects: number
  completed_projects: number
  total_tasks: number
  completed_tasks: number
  total_users: number
  total_clients: number
  total_revenue: number
  monthly_revenue: number[]
  project_status_distribution: Record<string, number>
  task_status_distribution: Record<string, number>
}

// Settings types
export interface UserSettings {
  id: string
  user_id: string
  theme: 'light' | 'dark' | 'system'
  language: 'en' | 'ru'
  notifications: {
    email: boolean
    push: boolean
    sms: boolean
  }
  privacy: {
    profile_visible: boolean
    activity_visible: boolean
  }
  created_at: string
  updated_at: string
}

export interface UpdateUserSettingsRequest {
  theme?: 'light' | 'dark' | 'system'
  language?: 'en' | 'ru'
  notifications?: {
    email?: boolean
    push?: boolean
    sms?: boolean
  }
  privacy?: {
    profile_visible?: boolean
    activity_visible?: boolean
  }
} 