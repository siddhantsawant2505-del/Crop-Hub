import User from '../models/User.js';
import logger from './logger.js';

const SEED_USER = {
  name: 'Demo Farmer',
  email: 'demo@crophub.com',
  password: 'password123',
  landSize: 15,
  farmLocation: {
    type: 'Point',
    coordinates: [77.5946, 12.9716],
    address: 'Bangalore, Karnataka'
  }
};

export const seedDemoUser = async () => {
  try {
    const existingUser = await User.findOne({ email: SEED_USER.email });

    if (!existingUser) {
      const user = await User.create(SEED_USER);
      user.setBudget(200000);
      await user.save();

      logger.info('Demo user created successfully', {
        email: SEED_USER.email,
        password: 'password123'
      });
    } else {
      logger.debug('Demo user already exists');
    }
  } catch (error) {
    logger.error('Error seeding demo user:', error);
  }
};

export const seedDatabase = async () => {
  logger.info('Seeding database...');
  await seedDemoUser();
  logger.info('Database seeding completed');
};
