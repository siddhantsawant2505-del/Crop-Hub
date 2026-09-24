import express from 'express';
import dns from 'dns';
import 'dotenv/config';

// Force Node to use reliable DNS servers for MongoDB SRV resolution
dns.setServers(['8.8.8.8', '8.8.4.4']);
import cors from 'cors';
import helmet from 'helmet';
import rateLimit from 'express-rate-limit';
import morgan from 'morgan';
import path from 'path';
import { fileURLToPath } from 'url';
import connectDB from './config/db.js';
import errorHandler from './middleware/errorHandler.js';

import authRoutes from './routes/authRoutes.js';
import soilRoutes from './routes/soilRoutes.js';
import cropRoutes from './routes/cropRoutes.js';
import marketRoutes from './routes/marketRoutes.js';
import fathomRoutes from './routes/fathomRoutes.js';
import logisticsRoutes from './routes/logisticsRoutes.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);



const app = express();

connectDB();

app.use(helmet({
  crossOriginResourcePolicy: { policy: "cross-origin" }
}));

const limiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 100,
  message: 'Too many requests from this IP, please try again later'
});
app.use('/api/', limiter);

app.use(cors({
  origin: process.env.CORS_ORIGIN || 'http://localhost:8080',
  credentials: true
}));

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.use('/uploads', express.static(path.join(__dirname, '../uploads')));

if (process.env.NODE_ENV === 'development') {
  app.use(morgan('dev'));
}

app.get('/api/health', (req, res) => {
  res.status(200).json({
    success: true,
    message: 'CropHub API is running',
    timestamp: new Date().toISOString()
  });
});

app.use('/api/auth', authRoutes);
app.use('/api/soil', soilRoutes);
app.use('/api/crop', cropRoutes);
app.use('/api/market', marketRoutes);
app.use('/api/fathom', fathomRoutes);
app.use('/api/logistics', logisticsRoutes);

app.use((req, res) => {
  res.status(404).json({
    success: false,
    message: 'Route not found'
  });
});

app.use(errorHandler);

const PORT = process.env.PORT || 5000;

app.listen(PORT, () => {
  console.log(`
╔═══════════════════════════════════════════════╗
║                                               ║
║         🌾  CropHub API Server  🌾           ║
║                                               ║
║  Environment: ${process.env.NODE_ENV || 'development'}                      ║
║  Port: ${PORT}                                   ║
║  Database: MongoDB                            ║
║                                               ║
╚═══════════════════════════════════════════════╝
  `);
});

process.on('unhandledRejection', (err) => {
  console.error('Unhandled Rejection:', err);
  process.exit(1);
});
