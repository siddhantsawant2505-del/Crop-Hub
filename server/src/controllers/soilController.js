import SoilAnalysis from '../models/SoilAnalysis.js';
import { uploadToS3 } from '../services/s3Service.js';
import FormData from 'form-data';
import axios from 'axios';

const TERRA_LAYER_URL = process.env.TERRA_LAYER_URL || 'http://localhost:8000/terra';
export const analyzeSoil = async (req, res, next) => {
  try {
    if (!req.file) {
      return res.status(400).json({
        success: false,
        message: 'Please upload a soil image'
      });
    }

    const { lat = 34.05, lon = -118.24, survey = '{"texture":"Unknown"}' } = req.body;

    const uploadResult = await uploadToS3(req.file, 'soil-images');

    const soilAnalysis = await SoilAnalysis.create({
      user: req.user?._id || null,
      imageUrl: uploadResult.url,
      status: 'processing'
    });

    let terraReport = null;
    try {
      const formData = new FormData();
      formData.append('image', req.file.buffer, { filename: req.file.originalname, contentType: req.file.mimetype });
      formData.append('lat', lat.toString());
      formData.append('lon', lon.toString());
      formData.append('survey', typeof survey === 'string' ? survey : JSON.stringify(survey));

      const response = await axios.post(`${TERRA_LAYER_URL}/api/analyze`, formData, {
        headers: {
          ...formData.getHeaders()
        },
        timeout: 60000
      });
      terraReport = response.data.report;
    } catch(err) {
      const detail = err.response?.data?.detail || err.message;
      console.error('Terra Layer error:', detail);
      terraReport = { error: detail };
    }

    soilAnalysis.mlPredictionData = terraReport;
    soilAnalysis.status = 'completed';

    await soilAnalysis.save();

    res.status(201).json({
      success: true,
      data: {
        analysis: {
          id: soilAnalysis._id,
          imageUrl: soilAnalysis.imageUrl,
          status: soilAnalysis.status,
          createdAt: soilAnalysis.createdAt,
          terraReport: terraReport 
        }
      }
    });
  } catch (error) {
    next(error);
  }
};

export const getSoilAnalyses = async (req, res, next) => {
  try {
    const page = parseInt(req.query.page) || 1;
    const limit = parseInt(req.query.limit) || 10;
    const skip = (page - 1) * limit;

    const analyses = await SoilAnalysis.find(req.user ? { user: req.user._id } : {})
      .sort({ createdAt: -1 })
      .skip(skip)
      .limit(limit);

   const total = await SoilAnalysis.countDocuments(req.user ? { user: req.user._id } : {});

    res.status(200).json({
      success: true,
      data: {
        analyses: analyses.map(a => ({
          id: a._id,
          imageUrl: a.imageUrl,
          status: a.status,
          createdAt: a.createdAt,
          terraReport: a.mlPredictionData
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

export const getSoilAnalysisById = async (req, res, next) => {
  try {
    const analysis = await SoilAnalysis.findOne({
      _id: req.params.id,
      user: req.user._id
    });

    if (!analysis) {
      return res.status(404).json({
        success: false,
        message: 'Soil analysis not found'
      });
    }

    res.status(200).json({
      success: true,
      data: {
        analysis: {
          id: analysis._id,
          imageUrl: analysis.imageUrl,
          status: analysis.status,
          createdAt: analysis.createdAt,
          terraReport: analysis.mlPredictionData
        }
      }
    });
  } catch (error) {
    next(error);
  }
};
