import MarketAnalysis from '../models/MarketAnalysis.js';
import { analyzeMarkets, getMarketPrices } from '../services/marketService.js';

export const analyzeMarket = async (req, res, next) => {
  try {
    const { cropType, weightTons, farmLocation } = req.body;

    if (!cropType || !weightTons || !farmLocation) {
      return res.status(400).json({
        success: false,
        message: 'Please provide cropType, weightTons, and farmLocation'
      });
    }

    if (!farmLocation.coordinates || farmLocation.coordinates.length !== 2) {
      return res.status(400).json({
        success: false,
        message: 'farmLocation must include coordinates [longitude, latitude]'
      });
    }

    const analysisResult = await analyzeMarkets(cropType, weightTons, farmLocation);

    const marketAnalysis = await MarketAnalysis.create({
      user: req.user._id,
      cropType,
      weightTons,
      farmLocation,
      markets: analysisResult.markets,
      bestMarket: analysisResult.bestMarket
    });

    res.status(201).json({
      success: true,
      data: {
        analysis: {
          id: marketAnalysis._id,
          cropType: marketAnalysis.cropType,
          weightTons: marketAnalysis.weightTons,
          markets: marketAnalysis.markets,
          bestMarket: marketAnalysis.bestMarket,
          createdAt: marketAnalysis.createdAt
        }
      }
    });
  } catch (error) {
    next(error);
  }
};

export const getMarketAnalyses = async (req, res, next) => {
  try {
    const page = parseInt(req.query.page) || 1;
    const limit = parseInt(req.query.limit) || 10;
    const skip = (page - 1) * limit;

    const analyses = await MarketAnalysis.find({ user: req.user._id })
      .sort({ createdAt: -1 })
      .skip(skip)
      .limit(limit);

    const total = await MarketAnalysis.countDocuments({ user: req.user._id });

    res.status(200).json({
      success: true,
      data: {
        analyses: analyses.map(a => ({
          id: a._id,
          cropType: a.cropType,
          weightTons: a.weightTons,
          markets: a.markets,
          bestMarket: a.bestMarket,
          createdAt: a.createdAt
        })),
        pagination: {
          page,
          limit,
          total,
          pages: Math.ceil(total / limit)
        }
      }
    });
  } catch (error) {
    next(error);
  }
};

export const getPrices = async (req, res, next) => {
  try {
    const { cropType } = req.query;

    if (!cropType) {
      return res.status(400).json({
        success: false,
        message: 'Please provide cropType'
      });
    }

    const prices = await getMarketPrices(cropType);

    res.status(200).json({
      success: true,
      data: {
        cropType,
        prices
      }
    });
  } catch (error) {
    next(error);
  }
};
