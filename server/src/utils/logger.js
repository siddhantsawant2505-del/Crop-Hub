const LOG_LEVELS = {
  ERROR: 'ERROR',
  WARN: 'WARN',
  INFO: 'INFO',
  DEBUG: 'DEBUG'
};

const colors = {
  ERROR: '\x1b[31m',
  WARN: '\x1b[33m',
  INFO: '\x1b[36m',
  DEBUG: '\x1b[35m',
  RESET: '\x1b[0m'
};

const formatMessage = (level, message, meta = {}) => {
  const timestamp = new Date().toISOString();
  const color = colors[level] || colors.RESET;
  const metaStr = Object.keys(meta).length > 0 ? JSON.stringify(meta, null, 2) : '';

  return `${color}[${timestamp}] [${level}]${colors.RESET} ${message} ${metaStr}`;
};

export const logger = {
  error: (message, meta = {}) => {
    console.error(formatMessage(LOG_LEVELS.ERROR, message, meta));
  },

  warn: (message, meta = {}) => {
    console.warn(formatMessage(LOG_LEVELS.WARN, message, meta));
  },

  info: (message, meta = {}) => {
    console.log(formatMessage(LOG_LEVELS.INFO, message, meta));
  },

  debug: (message, meta = {}) => {
    if (process.env.NODE_ENV === 'development') {
      console.log(formatMessage(LOG_LEVELS.DEBUG, message, meta));
    }
  }
};

export default logger;
