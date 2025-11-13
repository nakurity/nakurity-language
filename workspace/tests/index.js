// tests/index.js
'use strict';

const path = require('path');
const fs = require('fs');
const { Information } = require('./information');

(async function main() {
  const rootDir = path.resolve(__dirname, '..'); // workspace/
  const testsDir = __dirname;
  const workieDir = path.join(testsDir, '.workie');
  const nakieDir = path.join(testsDir, '.nakie');
  const shadowDir = path.join(testsDir, 'sandbox', 'shadow');

  const info = new Information({
    rootDir,
    testsDir,
    workieDir,
    nakieDir,
    shadowDir,
    logger: console
  });

  // Materialize shadow sandbox from src/static with an explicit whitelist
  const srcDir = path.join(rootDir, 'src');
  const staticDir = path.join(rootDir, 'static');
  Information.materializeShadow({
    srcDir,
    staticDir,
    shadowDir,
    whitelist: [
      // Add only what nakie files need:
      // { from: 'src/runtime.py' },
      // { from: 'static/config.yaml' },
    ]
  });

  // Auto-discover tests in .passie
  const passieDir = path.join(testsDir, '.passie');
  const files = fs.existsSync(passieDir) ? fs.readdirSync(passieDir) : [];
  const testFiles = files.filter(f => f.endsWith('.test.js'));

  if (testFiles.length === 0) {
    console.warn('No tests found in .passie');
  }

  const results = [];

  for (const file of testFiles) {
    const abs = path.join(passieDir, file);
    try {
      const mod = require(abs);
      if (typeof mod !== 'function') {
        console.warn(`Skipping ${file}: module should export a function(info)`);
        continue;
      }
      // Let the test file register its steps using Information
      await Promise.resolve(mod(info));

      // Execute the registered steps for this test
      const summary = await info.execute({ bail: false });
      results.push({ file, summary });

      // Reset for next test file
      info._registered = [];
    } catch (err) {
      console.error(`Error loading test ${file}: ${err.message}`);
      results.push({
        file,
        summary: {
          total: 1,
          passed: 0,
          failed: 1,
          results: [{ name: `load:${file}`, status: 'failed', error: { message: err.message } }]
        }
      });
      // continue to next test
      info._registered = [];
    }
  }

  // Aggregate and exit code
  const total = results.reduce((a, r) => a + r.summary.total, 0);
  const passed = results.reduce((a, r) => a + r.summary.passed, 0);
  const failed = results.reduce((a, r) => a + r.summary.failed, 0);

  console.log(`\n=== Summary ===`);
  console.log(`Total: ${total} | Passed: ${passed} | Failed: ${failed}`);

  process.exitCode = failed > 0 ? 1 : 0;
})();
