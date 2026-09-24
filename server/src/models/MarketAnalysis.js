import mongoose from 'mongoose';

const MarketOptionSchema = new mongoose.Schema({
  name: {
    type: String,
    required: true
  },
  distance: {
    type: String,
    required: true
  },
  distanceKm: {
    type: Number,
    required: true
  },
  price: {
    type: String,
    required: true
  },
  pricePerQuintal: {
    type: Number,
    required: true
  },
  transport: {
    type: String,
    required: true
  },
  transportCost: {
    type: Number,
    required: true
  },
  rent: {
    type: String,
    required: true
  },
  rentCost: {
    type: Number,
    required: true
  },
  trueProfit: {
    type: String,
    required: true
  },
  trueProfitValue: {
    type: Number,
    required: true
  },
  best: {
    type: Boolean,
    default: false
  },
  location: {
    type: {
      type: String,
      enum: ['Point'],
      default: 'Point'
    },
    coordinates: {
      type: [Number],
      default: [0, 0]
    }
  }
}, { _id: false });

const MarketAnalysisSchema = new mongoose.Schema({
  user: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true
  },
  cropType: {
    type: String,
    required: true
  },
  weightTons: {
    type: Number,
    required: true,
    min: 0
  },
  farmLocation: {
    type: {
      type: String,
      enum: ['Point'],
      default: 'Point'
    },
    coordinates: {
      type: [Number],
      required: true
    }
  },
  markets: [MarketOptionSchema],
  bestMarket: {
    type: String,
    default: ''
  },
  createdAt: {
    type: Date,
    default: Date.now
  }
}, {
  timestamps: true
});

MarketAnalysisSchema.index({ user: 1, createdAt: -1 });
MarketAnalysisSchema.index({ 'farmLocation.coordinates': '2dsphere' });

const MarketAnalysis = mongoose.models.MarketAnalysis || mongoose.model('MarketAnalysis', MarketAnalysisSchema);

export default MarketAnalysis;
