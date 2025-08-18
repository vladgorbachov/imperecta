import crypto from 'crypto'

const getKey = (): Buffer => {
  const secret = process.env.ENCRYPTION_KEY || ''
  // Derive a 32-byte key from the provided secret using scrypt
  return crypto.scryptSync(secret || 'default-dev-secret', 'imperecta-salt', 32)
}

export const encryptSecret = (plainText: string): string => {
  const iv = crypto.randomBytes(12)
  const key = getKey()
  const cipher = crypto.createCipheriv('aes-256-gcm', key, iv)
  const ciphertext = Buffer.concat([cipher.update(plainText, 'utf8'), cipher.final()])
  const authTag = cipher.getAuthTag()
  return [iv.toString('base64'), authTag.toString('base64'), ciphertext.toString('base64')].join(':')
}

export const decryptSecret = (encrypted: string): string => {
  const [ivB64, tagB64, dataB64] = encrypted.split(':')
  const iv = Buffer.from(ivB64, 'base64')
  const authTag = Buffer.from(tagB64, 'base64')
  const data = Buffer.from(dataB64, 'base64')
  const key = getKey()
  const decipher = crypto.createDecipheriv('aes-256-gcm', key, iv)
  decipher.setAuthTag(authTag)
  const plain = Buffer.concat([decipher.update(data), decipher.final()])
  return plain.toString('utf8')
}


