import express from 'express';
import { optimize, getNearbyMandis, getCrops, getFees } from '../controllers/logisticsController.js';

const router = express.Router();

router.post('/optimize', optimize);
router.post('/mandis/nearby', getNearbyMandis);
router.get('/crops', getCrops);
router.get('/config/fees', getFees);

export default router;
