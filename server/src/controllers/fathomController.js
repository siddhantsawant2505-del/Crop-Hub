import axios from 'axios';

const FATHOM_LAYER_URL = process.env.FATHOM_LAYER_URL || 'http://localhost:8000/fathom';

export const getRecommendations = async (req, res, next) => {
  try {
    const { soil_type, soil_quality, land_acres, budget_inr, lat, lon } = req.body;

    if (!soil_type || soil_quality === undefined || land_acres === undefined || budget_inr === undefined) {
      return res.status(400).json({
        success: false,
        message: 'Missing required parameters: soil_type, soil_quality, land_acres, or budget_inr'
      });
    }

    const response = await axios.post(`${FATHOM_LAYER_URL}/recommend`, {
      soil_type,
      soil_quality: Number(soil_quality),
      land_acres: Number(land_acres),
      budget_inr: Number(budget_inr),
      lat: lat ? Number(lat) : null,
      lon: lon ? Number(lon) : null
    });

    res.status(200).json({
      success: true,
      data: response.data
    });
  } catch (error) {
    if (error.response) {
      console.error('Fathom Layer error response:', error.response.data);
      return res.status(error.response.status).json({
        success: false,
        message: error.response.data.detail || 'Error from Fathom Layer'
      });
    } else if (error.request) {
      console.error('Fathom Layer no response:', error.message);
      return res.status(503).json({
        success: false,
        message: 'Fathom Layer is unavailable'
      });
    } else {
      console.error('Fathom controller error:', error.message);
      next(error);
    }
  }
};
