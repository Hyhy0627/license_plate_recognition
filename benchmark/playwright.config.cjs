const { defineConfig } = require('@playwright/test');
const path = require('node:path');
const out = process.env.BENCHMARK_OUTPUT || path.resolve(__dirname, '../data/benchmarks/browser_latest');
module.exports = defineConfig({
  testDir: './ui', timeout: 60000, expect: { timeout: 15000 }, workers: 1, retries: 0,
  outputDir: path.join(out, 'browser-artifacts'),
  reporter: [['list'], ['html', { outputFolder: path.join(out, 'browser'), open: 'never' }],
    ['json', { outputFile: path.join(out, 'browser.json') }]],
  use: { baseURL: 'http://127.0.0.1:13000', channel: process.env.BENCHMARK_BROWSER || 'msedge',
    headless: true, viewport: { width: 1366, height: 900 },
    screenshot: 'only-on-failure', trace: 'retain-on-failure', video: 'off' },
  webServer: {
    command: 'npm run dev -- --port 13000 --hostname 127.0.0.1',
    cwd: path.resolve(__dirname, '../frontend'), url: 'http://127.0.0.1:13000/login',
    reuseExistingServer: false, timeout: 120000,
    env: { NEXT_DIST_DIR: '.next-benchmark', NEXT_PUBLIC_API_URL: 'http://127.0.0.1:18000' },
  },
});
