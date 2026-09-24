import CropPlan from '../models/CropPlan.js';
import User from '../models/User.js';
import { optimizeCrops } from '../services/mlService.js';

export const createCropPlan = async (req, res, next) => {
  try {
    const { budget, landSize, season } = req.body;

    if (!budget || budget <= 0) {
      return res.status(400).json({
        success: false,
        message: 'Please provide a valid budget'
      });
    }

    if (!landSize || landSize <= 0) {
      return res.status(400).json({
        success: false,
        message: 'Please provide a valid land size'
      });
    }

    const user = await User.findById(req.user._id);
    if (budget) {
      user.setBudget(budget);
      await user.save();
    }

    const mlOptimization = await optimizeCrops(budget, landSize);

    const allocations = mlOptimization.allocations || [];

    const totalAllocated = allocations.reduce((sum, a) => sum + a.acres, 0);
    const totalCost = allocations.reduce((sum, a) => sum + a.cost, 0);
    const totalRevenue = allocations.reduce((sum, a) => sum + a.expectedRevenue, 0);
    const expectedProfit = totalRevenue - totalCost;

    const cropPlan = await CropPlan.create({
      user: req.user._id,
      budget,
      landSize,
      allocations,
      summary: {
        totalAllocated,
        totalCost,
        totalRevenue,
        expectedProfit
      },
      season: season || '',
      mlOptimizationData: mlOptimization,
      status: 'active'
    });

    res.status(201).json({
      success: true,
      data: {
        plan: {
          id: cropPlan._id,
          budget: cropPlan.budget,
          landSize: cropPlan.landSize,
          allocations: cropPlan.allocations,
          summary: cropPlan.summary,
          season: cropPlan.season,
          status: cropPlan.status,
          createdAt: cropPlan.createdAt
        }
      }
    });
  } catch (error) {
    next(error);
  }
};

export const getCropPlans = async (req, res, next) => {
  try {
    const page = parseInt(req.query.page) || 1;
    const limit = parseInt(req.query.limit) || 10;
    const skip = (page - 1) * limit;

    const status = req.query.status || 'active';

    const query = { user: req.user._id };
    if (status) query.status = status;

    const plans = await CropPlan.find(query)
      .sort({ createdAt: -1 })
      .skip(skip)
      .limit(limit);

    const total = await CropPlan.countDocuments(query);

    res.status(200).json({
      success: true,
      data: {
        plans: plans.map(p => ({
          id: p._id,
          budget: p.budget,
          landSize: p.landSize,
          allocations: p.allocations,
          summary: p.summary,
          season: p.season,
          status: p.status,
          createdAt: p.createdAt
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

export const getCropPlanById = async (req, res, next) => {
  try {
    const plan = await CropPlan.findOne({
      _id: req.params.id,
      user: req.user._id
    });

    if (!plan) {
      return res.status(404).json({
        success: false,
        message: 'Crop plan not found'
      });
    }

    res.status(200).json({
      success: true,
      data: {
        plan: {
          id: plan._id,
          budget: plan.budget,
          landSize: plan.landSize,
          allocations: plan.allocations,
          summary: plan.summary,
          season: plan.season,
          status: plan.status,
          createdAt: plan.createdAt
        }
      }
    });
  } catch (error) {
    next(error);
  }
};

export const updateCropPlanStatus = async (req, res, next) => {
  try {
    const { status } = req.body;

    const validStatuses = ['draft', 'active', 'completed', 'archived'];
    if (!validStatuses.includes(status)) {
      return res.status(400).json({
        success: false,
        message: 'Invalid status'
      });
    }

    const plan = await CropPlan.findOne({
      _id: req.params.id,
      user: req.user._id
    });

    if (!plan) {
      return res.status(404).json({
        success: false,
        message: 'Crop plan not found'
      });
    }

    plan.status = status;
    await plan.save();

    res.status(200).json({
      success: true,
      data: {
        plan: {
          id: plan._id,
          status: plan.status,
          updatedAt: plan.updatedAt
        }
      }
    });
  } catch (error) {
    next(error);
  }
};
