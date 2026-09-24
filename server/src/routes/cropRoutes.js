import express from 'express';
import { createCropPlan, getCropPlans, getCropPlanById, updateCropPlanStatus } from '../controllers/cropController.js';
import { protect } from '../middleware/auth.js';
import { cropPlanValidation, idValidation } from '../middleware/validation.js';

const router = express.Router();

router.post('/plan', protect, cropPlanValidation, createCropPlan);
router.get('/plans', protect, getCropPlans);
router.get('/plans/:id', protect, idValidation, getCropPlanById);
router.patch('/plans/:id/status', protect, idValidation, updateCropPlanStatus);

export default router;
