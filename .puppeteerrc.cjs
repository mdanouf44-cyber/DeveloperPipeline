const { join } = require('path');

/**
 * @type {import("puppeteer").Configuration}
 */
module.exports = {
  // Changes the cache location for Puppeteer so it is bundled with the build
  cacheDirectory: join(__dirname, '.cache', 'puppeteer'),
};
