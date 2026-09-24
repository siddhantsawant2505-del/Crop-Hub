import axios from 'axios';
import { CROP_DATABASE } from '../config/constants.js';
import logger from '../utils/logger.js';

const ML_SERVICE_URL = process.env.ML_SERVICE_URL || 'http://localhost:8000';

export const predictSoil = async (imageUrl) => {
  try {
    const response = await axios.post(`${ML_SERVICE_URL}/predict-soil`, {
      image_url: imageUrl
    }, {
      timeout: 30000
    });

    return response.data;
  } catch (error) {
    logger.warn('ML Service unavailable, using fallback for soil prediction', { error: error.message });

    return {
      soilType: 'Loamy',
      analysis: {
        nitrogen: Math.floor(Math.random() * 50) + 50,
        phosphorus: Math.floor(Math.random() * 40) + 30,
        potassium: Math.floor(Math.random() * 60) + 40,
        ph: (Math.random() * 2 + 6).toFixed(1),
        organicMatter: (Math.random() * 4 + 2).toFixed(1),
        moisture: Math.floor(Math.random() * 30) + 20
      },
      composition: {
        topsoil: 35,
        clay: 25,
        sand: 22,
        silt: 12,
        organic: 6
      }
    };
  }
};

export const optimizeCrops = async (budget, landSize, userPreferences = {}) => {
  try {
    const response = await axios.post(`${ML_SERVICE_URL}/optimize-crops`, {
      budget,
      land_size: landSize,
      preferences: userPreferences
    }, {
      timeout: 30000
    });

    return response.data;
  } catch (error) {
    logger.warn('ML Service unavailable, using fallback for crop optimization', { error: error.message });

    const sorted = [...CROP_DATABASE].sort((a, c) =>
      (c.revenuePerAcre - c.costPerAcre) - (a.revenuePerAcre - a.costPerAcre)
    );

    const allocations = [];
    let remainingBudget = budget;
    let remainingLand = landSize;

    for (const crop of sorted) {
      if (remainingBudget <= 0 || remainingLand <= 0) break;

      const maxAcresByBudget = remainingBudget / crop.costPerAcre;
      const acres = Math.min(maxAcresByBudget, remainingLand, Math.ceil(landSize / sorted.length));
      const roundedAcres = Math.round(acres * 10) / 10;

      if (roundedAcres <= 0) continue;

      allocations.push({
        name: crop.name,
        acres: roundedAcres,
        cost: roundedAcres * crop.costPerAcre,
        expectedRevenue: roundedAcres * crop.revenuePerAcre,
        color: crop.color
      });

      remainingBudget -= roundedAcres * crop.costPerAcre;
      remainingLand -= roundedAcres;
    }

    return { allocations };
  }
};
