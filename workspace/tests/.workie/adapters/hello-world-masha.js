'use strict';

const { spawnSync } = require('child_process');
const path = require('path');

module.exports = (() => {
  // Resolve where your Python module lives
  const rootDir = path.resolve(__dirname, '../..'); // up to /tests
  const srcDir = path.join(rootDir, 'src');

  // Normally command: python -m src path/to/masha
  const scriptArg = path.join('masha-files', 'hello-world.masha');

  const result = spawnSync('python', ['-m', 'src', scriptArg], {
    cwd: rootDir,
    encoding: 'utf8',
  });

  const stdout = result.stdout?.trim() || '';
  const stderr = result.stderr?.trim() || '';

  // Optional: log what happened
  if (stderr) console.error('[masha error]', stderr);

  // Return what the language actually printed
  return {
    output: stdout,
    exitCode: result.status,
    ok: result.status === 0 && /hello world/i.test(stdout),
  };
})();
