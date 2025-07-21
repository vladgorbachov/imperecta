#!/usr/bin/env node

/**
 * Environment variables checker for NextAuth
 * Run with: node scripts/check-env.js
 */

const fs = require('fs')
const path = require('path')

// Load environment variables
require('dotenv').config({ path: '.env.local' })

// Also try to load from .env if .env.local doesn't exist
if (!process.env.NEXTAUTH_URL) {
  require('dotenv').config({ path: '.env' })
}

const requiredVars = [
  'NEXTAUTH_URL',
  'NEXTAUTH_SECRET'
]

const optionalVars = [
  'GOOGLE_CLIENT_ID',
  'GOOGLE_CLIENT_SECRET',
  'GITHUB_CLIENT_ID',
  'GITHUB_CLIENT_SECRET',
  'EMAIL_SERVER_HOST',
  'EMAIL_SERVER_PORT',
  'EMAIL_SERVER_USER',
  'EMAIL_SERVER_PASSWORD',
  'EMAIL_FROM',
  'DATABASE_URL'
]

console.log('🔍 Checking NextAuth environment variables...\n')

// Check required variables
console.log('📋 Required Variables:')
let allRequiredPresent = true

requiredVars.forEach(varName => {
  const value = process.env[varName]
  if (value) {
    console.log(`✅ ${varName}: ${varName.includes('SECRET') ? '***' : value}`)
  } else {
    console.log(`❌ ${varName}: MISSING`)
    allRequiredPresent = false
  }
})

console.log('\n📋 Optional Variables:')
let configuredProviders = []

optionalVars.forEach(varName => {
  const value = process.env[varName]
  if (value) {
    console.log(`✅ ${varName}: ${varName.includes('SECRET') || varName.includes('PASSWORD') ? '***' : value}`)
    
    // Track configured providers
    if (varName.includes('GOOGLE')) {
      configuredProviders.push('Google')
    } else if (varName.includes('GITHUB')) {
      configuredProviders.push('GitHub')
    } else if (varName.includes('EMAIL')) {
      configuredProviders.push('Email')
    }
  } else {
    console.log(`⚪ ${varName}: not set`)
  }
})

console.log('\n🔧 Configuration Summary:')
console.log(`Environment: ${process.env.NODE_ENV || 'development'}`)
console.log(`NextAuth URL: ${process.env.NEXTAUTH_URL || 'NOT SET'}`)

if (configuredProviders.length > 0) {
  console.log(`Configured OAuth providers: ${configuredProviders.join(', ')}`)
} else {
  console.log('OAuth providers: None configured (only credentials provider available)')
}

// Security checks
console.log('\n🔒 Security Checks:')
if (process.env.NEXTAUTH_SECRET) {
  const secretLength = process.env.NEXTAUTH_SECRET.length
  if (secretLength >= 32) {
    console.log(`✅ NEXTAUTH_SECRET length: ${secretLength} characters (good)`)
  } else {
    console.log(`⚠️  NEXTAUTH_SECRET length: ${secretLength} characters (should be at least 32)`)
  }
} else {
  console.log('❌ NEXTAUTH_SECRET: not set')
}

if (process.env.NODE_ENV === 'production') {
  if (process.env.NEXTAUTH_URL && !process.env.NEXTAUTH_URL.includes('localhost')) {
    console.log('✅ Production URL configured correctly')
  } else {
    console.log('⚠️  Production URL should not include localhost')
  }
}

console.log('\n📝 Next Steps:')
if (!allRequiredPresent) {
  console.log('❌ Fix missing required variables before starting the application')
  process.exit(1)
} else {
  console.log('✅ All required variables are set')
  console.log('🚀 You can start the application with: npm run dev')
}

// Check if .env.local exists
const envPath = path.join(process.cwd(), '.env.local')
if (!fs.existsSync(envPath)) {
  console.log('\n⚠️  .env.local file not found')
  console.log('📝 Create .env.local file with your environment variables')
  console.log('📖 See AUTH_SETUP.md for configuration instructions')
} 