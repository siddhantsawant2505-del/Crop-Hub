export const CROP_DATABASE = [
  {
    name: 'Maize',
    costPerAcre: 8500,
    revenuePerAcre: 18000,
    color: 'hsl(45 80% 50%)',
    growingSeason: 'Kharif',
    waterRequirement: 'Medium',
    soilType: ['Loamy', 'Clay']
  },
  {
    name: 'Soybean',
    costPerAcre: 7200,
    revenuePerAcre: 16000,
    color: 'hsl(153 72% 14%)',
    growingSeason: 'Kharif',
    waterRequirement: 'Medium',
    soilType: ['Loamy', 'Sandy']
  },
  {
    name: 'Wheat',
    costPerAcre: 6800,
    revenuePerAcre: 14500,
    color: 'hsl(40 100% 45%)',
    growingSeason: 'Rabi',
    waterRequirement: 'Low',
    soilType: ['Loamy', 'Clay']
  },
  {
    name: 'Rice',
    costPerAcre: 10200,
    revenuePerAcre: 22000,
    color: 'hsl(20 30% 22%)',
    growingSeason: 'Kharif',
    waterRequirement: 'High',
    soilType: ['Clay', 'Loamy']
  },
  {
    name: 'Cotton',
    costPerAcre: 9500,
    revenuePerAcre: 20000,
    color: 'hsl(200 40% 45%)',
    growingSeason: 'Kharif',
    waterRequirement: 'Medium',
    soilType: ['Loamy', 'Sandy']
  },
  {
    name: 'Sugarcane',
    costPerAcre: 12000,
    revenuePerAcre: 28000,
    color: 'hsl(120 40% 50%)',
    growingSeason: 'Year-round',
    waterRequirement: 'High',
    soilType: ['Loamy', 'Clay']
  },
  {
    name: 'Pulses',
    costPerAcre: 5500,
    revenuePerAcre: 12000,
    color: 'hsl(30 60% 50%)',
    growingSeason: 'Rabi',
    waterRequirement: 'Low',
    soilType: ['Loamy', 'Sandy']
  }
];

export const SOIL_TYPES = {
  LOAMY: 'Loamy',
  SANDY: 'Sandy',
  CLAY: 'Clay',
  SILT: 'Silt',
  PEATY: 'Peaty',
  CHALKY: 'Chalky',
  UNKNOWN: 'Unknown'
};

export const CROP_SEASONS = {
  KHARIF: 'Kharif',
  RABI: 'Rabi',
  ZAID: 'Zaid',
  YEAR_ROUND: 'Year-round'
};

export const MARKET_LOCATIONS = [
  {
    name: 'Mandi Alpha',
    coordinates: [77.5946, 12.9716],
    city: 'Bangalore',
    state: 'Karnataka'
  },
  {
    name: 'Mandi Beta',
    coordinates: [77.6031, 12.9634],
    city: 'Bangalore',
    state: 'Karnataka'
  },
  {
    name: 'Mandi Gamma',
    coordinates: [77.6208, 12.9279],
    city: 'Bangalore',
    state: 'Karnataka'
  },
  {
    name: 'Mandi Delta',
    coordinates: [77.5700, 12.9800],
    city: 'Bangalore',
    state: 'Karnataka'
  }
];

export const API_RESPONSE_MESSAGES = {
  SUCCESS: 'Operation completed successfully',
  CREATED: 'Resource created successfully',
  UPDATED: 'Resource updated successfully',
  DELETED: 'Resource deleted successfully',
  NOT_FOUND: 'Resource not found',
  UNAUTHORIZED: 'Not authorized to access this resource',
  VALIDATION_ERROR: 'Validation error',
  SERVER_ERROR: 'Internal server error'
};

export const FILE_UPLOAD_CONFIG = {
  MAX_FILE_SIZE: 10 * 1024 * 1024,
  ALLOWED_MIME_TYPES: ['image/jpeg', 'image/jpg', 'image/png'],
  ALLOWED_EXTENSIONS: ['jpeg', 'jpg', 'png']
};
