import axios from 'axios';
import { MARKET_LOCATIONS } from '../config/constants.js';
import logger from '../utils/logger.js';

const MOCK_MARKETS = MARKET_LOCATIONS.map((location, index) => ({
  name: location.name,
  location: { coordinates: location.coordinates },
  basePrice: 2400 + (index * 200) + Math.floor(Math.random() * 100)
}));

const calculateDistance = (lat1, lon1, lat2, lon2) => {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a =
    Math.sin(dLat/2) * Math.sin(dLat/2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon/2) * Math.sin(dLon/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  const distance = R * c;
  return Math.round(distance);
};

const calculateTransportCost = (distanceKm) => {
  const baseRate = 50;
  return Math.round(distanceKm * baseRate);
};

const calculateMarketRent = (distanceKm) => {
  const baseRent = 100;
  const additionalRent = Math.floor(distanceKm / 10) * 20;
  return baseRent + additionalRent;
};

export const analyzeMarkets = async (cropType, weightTons, farmLocation) => {
  try {
    const [farmLon, farmLat] = farmLocation.coordinates;

    const marketAnalysis = MOCK_MARKETS.map(market => {
      const [marketLon, marketLat] = market.location.coordinates;
      const distanceKm = calculateDistance(farmLat, farmLon, marketLat, marketLon);

      const pricePerQuintal = market.basePrice + (Math.random() * 200 - 100);
      const weightQuintals = weightTons * 10;
      const grossRevenue = pricePerQuintal * weightQuintals;

      const transportCost = calculateTransportCost(distanceKm);
      const rentCost = calculateMarketRent(distanceKm);

      const trueProfitValue = Math.round(grossRevenue - transportCost - rentCost);

      return {
        name: market.name,
        distance: `${distanceKm} km`,
        distanceKm,
        price: `₹${Math.round(pricePerQuintal)}/q`,
        pricePerQuintal: Math.round(pricePerQuintal),
        transport: `₹${transportCost}`,
        transportCost,
        rent: `₹${rentCost}`,
        rentCost,
        trueProfit: `₹${trueProfitValue.toLocaleString()}`,
        trueProfitValue,
        best: false,
        location: market.location
      };
    });

    marketAnalysis.sort((a, b) => b.trueProfitValue - a.trueProfitValue);

    if (marketAnalysis.length > 0) {
      marketAnalysis[0].best = true;
    }

    return {
      markets: marketAnalysis,
      bestMarket: marketAnalysis.length > 0 ? marketAnalysis[0].name : ''
    };
  } catch (error) {
    logger.error('Market Analysis Error:', error);
    throw error;
  }
};

export const getMarketPrices = async (cropType) => {
  try {
    return {
      averagePrice: 2500,
      minPrice: 2200,
      maxPrice: 3000,
      trend: 'rising'
    };
  } catch (error) {
    logger.error('Market Price Fetch Error:', error);
    throw error;
  }
};
