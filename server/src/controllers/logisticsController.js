import axios from 'axios';

const LOGISTICS_LAYER_URL = process.env.LOGISTICS_LAYER_URL || 'http://localhost:8000/logistics';

export const optimize = async (req, res, next) => {
  try {
    const response = await axios.post(`${LOGISTICS_LAYER_URL}/optimize`, req.body);
    res.status(200).json({
      success: true,
      data: response.data
    });
  } catch (error) {
    if (error.response) {
      console.error('Logistics Layer error response:', error.response.data);
      return res.status(error.response.status).json({
        success: false,
        message: error.response.data.detail || 'Error from Logistics Layer'
      });
    } else if (error.request) {
      console.error('Logistics Layer no response:', error.message);
      return res.status(503).json({
        success: false,
        message: 'Logistics Layer is unavailable'
      });
    } else {
      console.error('Logistics controller error:', error.message);
      next(error);
    }
  }
};

export const getNearbyMandis = async (req, res, next) => {
  try {
    const response = await axios.post(`${LOGISTICS_LAYER_URL}/mandis/nearby`, req.body);
    res.status(200).json({
      success: true,
      data: response.data
    });
  } catch (error) {
    next(error);
  }
};

export const getCrops = async (req, res, next) => {
  try {
    const response = await axios.get(`${LOGISTICS_LAYER_URL}/crops`);
    res.status(200).json({
      success: true,
      data: response.data
    });
  } catch (error) {
    next(error);
  }
};

export const getFees = async (req, res, next) => {
  try {
    const response = await axios.get(`${LOGISTICS_LAYER_URL}/config/fees`);
    res.status(200).json({
      success: true,
      data: response.data
    });
  } catch (error) {
    next(error);
  }
};
