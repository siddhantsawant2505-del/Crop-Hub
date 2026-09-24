import dotenv from 'dotenv';
import connectDB from '../config/db.js';
import { seedDatabase } from '../utils/seedData.js';
import logger from '../utils/logger.js';

dotenv.config();

const initializeDatabase = async () => {
  try {
    logger.info('Starting database initialization...');

    await connectDB();
    logger.info('Database connection established');

    await seedDatabase();
    logger.info('Database initialization completed successfully');

    process.exit(0);
  } catch (error) {
    logger.error('Database initialization failed:', error);
    process.exit(1);
  }
};

initializeDatabase();
