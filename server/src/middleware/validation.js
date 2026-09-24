import { body, param, query, validationResult } from 'express-validator';

export const validateRequest = (req, res, next) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res.status(400).json({
      success: false,
      errors: errors.array().map(err => ({
        field: err.path,
        message: err.msg
      }))
    });
  }
  next();
};

export const registerValidation = [
  body('name')
    .trim()
    .notEmpty()
    .withMessage('Name is required')
    .isLength({ min: 2, max: 100 })
    .withMessage('Name must be between 2 and 100 characters'),
  body('email')
    .trim()
    .notEmpty()
    .withMessage('Email is required')
    .isEmail()
    .withMessage('Please provide a valid email')
    .normalizeEmail(),
  body('password')
    .notEmpty()
    .withMessage('Password is required')
    .isLength({ min: 6 })
    .withMessage('Password must be at least 6 characters'),
  validateRequest
];

export const loginValidation = [
  body('email')
    .trim()
    .notEmpty()
    .withMessage('Email is required')
    .isEmail()
    .withMessage('Please provide a valid email')
    .normalizeEmail(),
  body('password')
    .notEmpty()
    .withMessage('Password is required'),
  validateRequest
];

export const cropPlanValidation = [
  body('budget')
    .notEmpty()
    .withMessage('Budget is required')
    .isNumeric()
    .withMessage('Budget must be a number')
    .custom(value => value > 0)
    .withMessage('Budget must be greater than 0'),
  body('landSize')
    .notEmpty()
    .withMessage('Land size is required')
    .isNumeric()
    .withMessage('Land size must be a number')
    .custom(value => value > 0)
    .withMessage('Land size must be greater than 0'),
  body('season')
    .optional()
    .trim()
    .isLength({ max: 100 })
    .withMessage('Season must be less than 100 characters'),
  validateRequest
];

export const marketAnalysisValidation = [
  body('cropType')
    .trim()
    .notEmpty()
    .withMessage('Crop type is required')
    .isLength({ min: 2, max: 50 })
    .withMessage('Crop type must be between 2 and 50 characters'),
  body('weightTons')
    .notEmpty()
    .withMessage('Weight in tons is required')
    .isNumeric()
    .withMessage('Weight must be a number')
    .custom(value => value > 0)
    .withMessage('Weight must be greater than 0'),
  body('farmLocation')
    .notEmpty()
    .withMessage('Farm location is required'),
  body('farmLocation.type')
    .equals('Point')
    .withMessage('Farm location type must be Point'),
  body('farmLocation.coordinates')
    .isArray({ min: 2, max: 2 })
    .withMessage('Coordinates must be an array of [longitude, latitude]'),
  body('farmLocation.coordinates.*')
    .isNumeric()
    .withMessage('Coordinates must be numbers'),
  validateRequest
];

export const idValidation = [
  param('id')
    .isMongoId()
    .withMessage('Invalid ID format'),
  validateRequest
];
