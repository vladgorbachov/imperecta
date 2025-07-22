#!/usr/bin/env node

/**
 * Environment variables checker
 * Run with: node shared/scripts/check-env.js
 */

const fs = require('fs')
const path = require('path')

// Load environment variables from .env
require('dotenv').config({ path: '.env' })

const requiredVars = [
  'VITE_SUPABASE_URL',
  'VITE_SUPABASE_ANON_KEY'
]

const optionalVars = [
  'VITE_APP_URL',
  'VITE_DATABASE_URL'
]

console.log('🔍 Checking environment variables...\n')

// Check required variables
console.log('📋 Required Variables:')
let allRequiredPresent = true

requiredVars.forEach(varName => {
  const value = process.env[varName]
  if (value) {
    console.log(`✅ ${varName}: ${value}`)
  } else {
    console.log(`❌ ${varName}: MISSING`)
    allRequiredPresent = false
  }
})

console.log('\n📋 Optional Variables:')

optionalVars.forEach(varName => {
  const value = process.env[varName]
  if (value) {
    console.log(`✅ ${varName}: ${value}`)
  } else {
    console.log(`⚪ ${varName}: not set`)
  }
})

console.log('\n🔧 Configuration Summary:')
console.log(`Environment: ${process.env.NODE_ENV || 'development'}`)
console.log(`App URL: ${process.env.VITE_APP_URL || 'http://localhost:3000'}`)
console.log(`Supabase URL: ${process.env.VITE_SUPABASE_URL || 'NOT SET'}`)
console.log(`Supabase ANON KEY: ${process.env.VITE_SUPABASE_ANON_KEY ? '***' : 'NOT SET'}`)

console.log('\n📝 Next Steps:')
if (!allRequiredPresent) {
  console.log('❌ Fix missing required variables before starting the application')
  process.exit(1)
} else {
  console.log('✅ All required variables are set')
  console.log('🚀 You can start the application with: npm run dev')
}

// Check if .env exists
const envPath = path.join(process.cwd(), '.env')
if (!fs.existsSync(envPath)) {
  console.log('\n⚠️  .env file not found')
  console.log('📝 Create .env file with your environment variables')
} 