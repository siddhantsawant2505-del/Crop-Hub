import crypto from 'crypto';

const algorithm = 'aes-256-cbc';

const getKey = () => {
  const key = process.env.ENCRYPTION_KEY;
  if (!key || key.length !== 32) {
    throw new Error('ENCRYPTION_KEY must be exactly 32 characters');
  }
  return Buffer.from(key, 'utf8');
};

const getIV = () => {
  const iv = process.env.ENCRYPTION_IV;
  if (!iv || iv.length !== 16) {
    throw new Error('ENCRYPTION_IV must be exactly 16 characters');
  }
  return Buffer.from(iv, 'utf8');
};

export const encrypt = (text) => {
  if (!text) return null;

  try {
    const cipher = crypto.createCipheriv(algorithm, getKey(), getIV());
    let encrypted = cipher.update(String(text), 'utf8', 'hex');
    encrypted += cipher.final('hex');
    return encrypted;
  } catch (error) {
    console.error('Encryption error:', error);
    throw new Error('Failed to encrypt data');
  }
};

export const decrypt = (encryptedText) => {
  if (!encryptedText) return null;

  try {
    const decipher = crypto.createDecipheriv(algorithm, getKey(), getIV());
    let decrypted = decipher.update(encryptedText, 'hex', 'utf8');
    decrypted += decipher.final('utf8');
    return decrypted;
  } catch (error) {
    console.error('Decryption error:', error);
    throw new Error('Failed to decrypt data');
  }
};
