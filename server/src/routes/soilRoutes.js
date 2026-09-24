import express from 'express';
import { analyzeSoil, getSoilAnalyses, getSoilAnalysisById } from '../controllers/soilController.js';
import { protect } from '../middleware/auth.js';
import upload from '../middleware/upload.js';
import { idValidation } from '../middleware/validation.js';

const router = express.Router();

router.post('/analyze',upload.single('soilImage'), analyzeSoil);
router.get('/', protect, getSoilAnalyses);
router.get('/:id', protect, idValidation, getSoilAnalysisById);

export default router;
