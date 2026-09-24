import mongoose from 'mongoose';

const SoilAnalysisSchema = new mongoose.Schema({
  user: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: false,
    default: null
  },
  imageUrl: {
    type: String,
    required: true
  },
  soilType: {
    type: String,
    enum: ['Loamy', 'Sandy', 'Clay', 'Silt', 'Peaty', 'Chalky', 'Unknown'],
    default: 'Unknown'
  },
  analysis: {
    nitrogen: {
      type: Number,
      min: 0,
      max: 200,
      default: 0
    },
    phosphorus: {
      type: Number,
      min: 0,
      max: 200,
      default: 0
    },
    potassium: {
      type: Number,
      min: 0,
      max: 200,
      default: 0
    },
    ph: {
      type: Number,
      min: 0,
      max: 14,
      default: 7
    },
    organicMatter: {
      type: Number,
      min: 0,
      max: 100,
      default: 0
    },
    moisture: {
      type: Number,
      min: 0,
      max: 100,
      default: 0
    }
  },
  composition: {
    topsoil: {
      type: Number,
      min: 0,
      max: 100,
      default: 0
    },
    clay: {
      type: Number,
      min: 0,
      max: 100,
      default: 0
    },
    sand: {
      type: Number,
      min: 0,
      max: 100,
      default: 0
    },
    silt: {
      type: Number,
      min: 0,
      max: 100,
      default: 0
    },
    organic: {
      type: Number,
      min: 0,
      max: 100,
      default: 0
    }
  },
  status: {
    type: String,
    enum: ['pending', 'processing', 'completed', 'failed'],
    default: 'pending'
  },
  mlPredictionData: {
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

SoilAnalysisSchema.index({ user: 1, createdAt: -1 });

const SoilAnalysis = mongoose.models.SoilAnalysis || mongoose.model('SoilAnalysis', SoilAnalysisSchema);

export default SoilAnalysis;
