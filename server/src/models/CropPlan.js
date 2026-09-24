import mongoose from 'mongoose';

const CropAllocationSchema = new mongoose.Schema({
  name: {
    type: String,
    required: true
  },
  acres: {
    type: Number,
    required: true,
    min: 0
  },
  cost: {
    type: Number,
    required: true,
    min: 0
  },
  expectedRevenue: {
    type: Number,
    required: true,
    min: 0
  },
  color: {
    type: String,
    default: '#000000'
  }
}, { _id: false });

const CropPlanSchema = new mongoose.Schema({
  user: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true
  },
  budget: {
    type: Number,
    required: true,
    min: 0
  },
  landSize: {
    type: Number,
    required: true,
    min: 0
  },
  allocations: [CropAllocationSchema],
  summary: {
    totalAllocated: {
      type: Number,
      default: 0
    },
    totalCost: {
      type: Number,
      default: 0
    },
    totalRevenue: {
      type: Number,
      default: 0
    },
    expectedProfit: {
      type: Number,
      default: 0
    }
  },
  status: {
    type: String,
    enum: ['draft', 'active', 'completed', 'archived'],
    default: 'active'
  },
  season: {
    type: String,
    default: ''
  },
  mlOptimizationData: {
    type: mongoose.Schema.Types.Mixed,
    default: {}
  },
  createdAt: {
    type: Date,
    default: Date.now
  }
}, {
  timestamps: true
});

CropPlanSchema.index({ user: 1, status: 1, createdAt: -1 });

const CropPlan = mongoose.models.CropPlan || mongoose.model('CropPlan', CropPlanSchema);

export default CropPlan;
