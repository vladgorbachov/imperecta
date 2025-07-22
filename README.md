# Imperecta

A modern project management application with React frontend and Node.js backend.

## Project Structure

```
imperecta/
├── frontend/          # React + Vite application
├── backend/           # Node.js + Express + Drizzle ORM
└── README.md
```

## Getting Started

### Prerequisites

- Node.js 18+ 
- PostgreSQL database
- npm or yarn

### Backend Setup

1. Navigate to backend directory:
```bash
cd backend
```

2. Install dependencies:
```bash
npm install
```

3. Configure environment variables:
   - Copy `.env.example` to `.env` (if exists)
   - Update database connection string in `.env`

4. Run database migrations:
```bash
npm run db:migrate
```

5. Start development server:
```bash
npm run dev
```

Backend will be available at `http://localhost:3001`

### Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Configure environment variables:
   - Copy `.env.example` to `.env` (if exists)
   - Update API URL and Supabase credentials

4. Start development server:
```bash
npm run dev
```

Frontend will be available at `http://localhost:5173`

## Development

### Backend API Endpoints

- `GET /api/health` - Health check
- `GET /api` - API information
- `GET /api/users` - Get all users
- `POST /api/users` - Create user
- `GET /api/users/:id` - Get user by ID
- `PUT /api/users/:id` - Update user
- `DELETE /api/users/:id` - Delete user

### Database

The project uses Drizzle ORM with PostgreSQL. Database schema is defined in `backend/src/api/schema.ts`.

### Available Scripts

**Backend:**
- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run start` - Start production server
- `npm run db:generate` - Generate migrations
- `npm run db:migrate` - Run migrations
- `npm run db:studio` - Open Drizzle Studio

**Frontend:**
- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## Environment Variables

### Backend (.env)
```
APP_URL=http://localhost:3001
PORT=3001
DATABASE_URL=postgresql://user:password@localhost:5432/database
SUPABASE_URL=your-supabase-url
SUPABASE_ANON_KEY=your-supabase-anon-key
NODE_ENV=development
```

### Frontend (.env)
```
VITE_APP_URL=http://localhost:5173
VITE_API_URL=http://localhost:3001
VITE_SUPABASE_URL=your-supabase-url
VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
NODE_ENV=development
```

## Technologies

**Frontend:**
- React 19
- Vite
- TypeScript
- Tailwind CSS
- Radix UI
- React Router
- Supabase Auth

**Backend:**
- Node.js
- Express
- TypeScript
- Drizzle ORM
- PostgreSQL
- CORS
- Helmet
- Morgan

## License

MIT 