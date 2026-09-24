import express from 'express';
import { analyzeMarket, getMarketAnalyses, getPrices } from '../controllers/marketController.js';
import { protect } from '../middleware/auth.js';
import { marketAnalysisValidation } from '../middleware/validation.js';

const router = express.Router();

router.post('/analyze', protect, marketAnalysisValidation, analyzeMarket);
router.get('/analyses', protect, getMarketAnalyses);
router.get('/prices', protect, getPrices);

export default router;
