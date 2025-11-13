'use strict';

const { spawnSync } = require('child_process');
const path = require('path');

module.exports = (() => {
  // Resolve where your Python module lives
  const rootDir = path.resolve(__dirname, '../../'); // up to /tests
  const srcDir = path.join(rootDir, 'sandbox/shadow');

  // Normally command: python -m src path/to/masha
  const scriptArg = path.join(rootDir, '.workie', 'masha-files', 'hello-world.masha');

  // TODO: sandbox this runner to use our own spawner with restrictions
  const result = spawnSync('python', ['-m', 'src', scriptArg], {
    cwd: srcDir,
    encoding: 'utf8',
  });

  const stdout = result.stdout?.trim() || undefined;
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
