import AWS from 'aws-sdk';
import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const USE_LOCAL_STORAGE = process.env.AWS_ACCESS_KEY_ID === 'mock-access-key' ||
                          process.env.AWS_ACCESS_KEY_ID === 'your-aws-access-key' ||
                          !process.env.AWS_ACCESS_KEY_ID ||
                          process.env.USE_LOCAL_STORAGE === 'true';

let s3;
if (!USE_LOCAL_STORAGE) {
  s3 = new AWS.S3({
    accessKeyId: process.env.AWS_ACCESS_KEY_ID,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
    region: process.env.AWS_REGION
  });
}

const ensureUploadDirectory = () => {
  const uploadDir = path.join(__dirname, '../../uploads');
  if (!fs.existsSync(uploadDir)) {
    fs.mkdirSync(uploadDir, { recursive: true });
  }
  return uploadDir;
};

export const uploadToS3 = async (file, folder = 'soil-images') => {
  try {
    const fileExtension = file.originalname.split('.').pop();
    const fileName = `${folder}/${crypto.randomBytes(16).toString('hex')}.${fileExtension}`;

    if (USE_LOCAL_STORAGE) {
      return await _saveToLocal(file, folder, fileName);
    }

    const params = {
      Bucket: process.env.AWS_S3_BUCKET,
      Key: fileName,
      Body: file.buffer,
      ContentType: file.mimetype
      // Removed ACL: 'public-read' as it causes errors on buckets with ACLs disabled
    };

    try {
      const result = await s3.upload(params).promise();
      return {
        url: result.Location,
        key: result.Key
      };
    } catch (s3Error) {
      console.warn('S3 Upload failed, falling back to local storage:', s3Error.message);
      // Fallback to local storage logic
      return await _saveToLocal(file, folder, fileName);
    }
  } catch (error) {
    console.error('File Upload Error:', error);
    throw new Error('Failed to upload file');
  }
};

const _saveToLocal = async (file, folder, fileName) => {
  const uploadDir = ensureUploadDirectory();
  const folderPath = path.join(uploadDir, folder);

  if (!fs.existsSync(folderPath)) {
    fs.mkdirSync(folderPath, { recursive: true });
  }

  const filePath = path.join(uploadDir, fileName);
  fs.writeFileSync(filePath, file.buffer);

  const baseUrl = process.env.BASE_URL || `http://localhost:${process.env.PORT || 5000}`;
  return {
    url: `${baseUrl}/uploads/${fileName}`,
    key: fileName
  };
};

export const deleteFromS3 = async (key) => {
  try {
    if (USE_LOCAL_STORAGE) {
      const uploadDir = ensureUploadDirectory();
      const filePath = path.join(uploadDir, key);

      if (fs.existsSync(filePath)) {
        fs.unlinkSync(filePath);
      }
      return true;
    }

    const params = {
      Bucket: process.env.AWS_S3_BUCKET,
      Key: key
    };

    await s3.deleteObject(params).promise();
    return true;
  } catch (error) {
    console.error('S3 Delete Error:', error);
    throw new Error('Failed to delete file from S3');
  }
};
