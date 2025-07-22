import {
  Project,
  Task,
  Client,
  AnalyticsData,
  CreateProjectRequest,
  UpdateProjectRequest,
  CreateTaskRequest,
  UpdateTaskRequest,
  CreateClientRequest,
  UpdateClientRequest,
} from './types'

// Mock data for development
export const mockProjects: Project[] = [
  {
    id: '1',
    name: 'Website Redesign',
    description: 'Complete redesign of company website',
    status: 'active',
    priority: 'high',
    start_date: '2024-01-01T00:00:00Z',
    end_date: '2024-03-31T00:00:00Z',
    budget: '15000',
    created_by: '1',
    assigned_to: ['1', '2'],
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: '2',
    name: 'Mobile App Development',
    description: 'iOS and Android app development',
    status: 'active',
    priority: 'urgent',
    start_date: '2024-02-01T00:00:00Z',
    end_date: '2024-06-30T00:00:00Z',
    budget: '50000',
    created_by: '1',
    assigned_to: ['2', '3'],
    created_at: '2024-02-01T00:00:00Z',
    updated_at: '2024-02-01T00:00:00Z',
  },
]

export const mockTasks: Task[] = [
  {
    id: '1',
    title: 'Design Homepage',
    description: 'Create new homepage design',
    status: 'in-progress',
    priority: 'high',
    project_id: '1',
    assigned_to: '2',
    created_by: '1',
    due_date: '2024-01-15T00:00:00Z',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: '2',
    title: 'Implement Navigation',
    description: 'Build responsive navigation menu',
    status: 'todo',
    priority: 'medium',
    project_id: '1',
    assigned_to: '3',
    created_by: '1',
    due_date: '2024-01-20T00:00:00Z',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
]

export const mockClients: Client[] = [
  {
    id: '1',
    name: 'Acme Corporation',
    email: 'contact@acme.com',
    phone: '+1-555-0123',
    company: 'Acme Corp',
    address: '123 Business St, City, State 12345',
    notes: 'Premium client, high priority',
    created_by: '1',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
]

export const mockAnalytics: AnalyticsData = {
  total_projects: 2,
  active_projects: 2,
  completed_projects: 0,
  total_tasks: 2,
  completed_tasks: 0,
  total_users: 3,
  total_clients: 1,
  total_revenue: 65000,
  monthly_revenue: [15000, 50000],
  project_status_distribution: {
    active: 2,
    completed: 0,
    'on-hold': 0,
    cancelled: 0,
  },
  task_status_distribution: {
    todo: 1,
    'in-progress': 1,
    review: 0,
    completed: 0,
  },
}

// API functions (mock implementations)
export const api = {
  // Projects
  getProjects: async (): Promise<Project[]> => {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 500))
    return mockProjects
  },

  createProject: async (data: CreateProjectRequest): Promise<Project> => {
    await new Promise(resolve => setTimeout(resolve, 500))
    const newProject: Project = {
      id: Date.now().toString(),
      ...data,
      created_by: '1', // Mock user ID
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    mockProjects.push(newProject)
    return newProject
  },

  updateProject: async (id: string, data: UpdateProjectRequest): Promise<Project> => {
    await new Promise(resolve => setTimeout(resolve, 500))
    const project = mockProjects.find(p => p.id === id)
    if (!project) throw new Error('Project not found')
    
    Object.assign(project, data, { updated_at: new Date().toISOString() })
    return project
  },

  deleteProject: async (id: string): Promise<void> => {
    await new Promise(resolve => setTimeout(resolve, 500))
    const index = mockProjects.findIndex(p => p.id === id)
    if (index > -1) mockProjects.splice(index, 1)
  },

  // Tasks
  getTasks: async (): Promise<Task[]> => {
    await new Promise(resolve => setTimeout(resolve, 500))
    return mockTasks
  },

  createTask: async (data: CreateTaskRequest): Promise<Task> => {
    await new Promise(resolve => setTimeout(resolve, 500))
    const newTask: Task = {
      id: Date.now().toString(),
      ...data,
      created_by: '1', // Mock user ID
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    mockTasks.push(newTask)
    return newTask
  },

  updateTask: async (id: string, data: UpdateTaskRequest): Promise<Task> => {
    await new Promise(resolve => setTimeout(resolve, 500))
    const task = mockTasks.find(t => t.id === id)
    if (!task) throw new Error('Task not found')
    
    Object.assign(task, data, { updated_at: new Date().toISOString() })
    return task
  },

  deleteTask: async (id: string): Promise<void> => {
    await new Promise(resolve => setTimeout(resolve, 500))
    const index = mockTasks.findIndex(t => t.id === id)
    if (index > -1) mockTasks.splice(index, 1)
  },

  // Clients
  getClients: async (): Promise<Client[]> => {
    await new Promise(resolve => setTimeout(resolve, 500))
    return mockClients
  },

  createClient: async (data: CreateClientRequest): Promise<Client> => {
    await new Promise(resolve => setTimeout(resolve, 500))
    const newClient: Client = {
      id: Date.now().toString(),
      ...data,
      created_by: '1', // Mock user ID
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    mockClients.push(newClient)
    return newClient
  },

  updateClient: async (id: string, data: UpdateClientRequest): Promise<Client> => {
    await new Promise(resolve => setTimeout(resolve, 500))
    const client = mockClients.find(c => c.id === id)
    if (!client) throw new Error('Client not found')
    
    Object.assign(client, data, { updated_at: new Date().toISOString() })
    return client
  },

  deleteClient: async (id: string): Promise<void> => {
    await new Promise(resolve => setTimeout(resolve, 500))
    const index = mockClients.findIndex(c => c.id === id)
    if (index > -1) mockClients.splice(index, 1)
  },

  // Analytics
  getAnalytics: async (): Promise<AnalyticsData> => {
    await new Promise(resolve => setTimeout(resolve, 500))
    return mockAnalytics
  },
} 