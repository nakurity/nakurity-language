// tests/.passie/console_printing.test.js
'use strict';

module.exports = function (info) {
  // Use sandboxed workie resource (e.g., JSON config or helper adapter)
  const cfg = info.require('masha-files/hello-world.masha');

  // Load nakie expectations
  const nakie = info.expect('print_to_console', { mode: 'strict' });

  // Register test steps
  info.register('configuration must have required keys', async () => {
    nakie.Nakie.trace('config-loaded', cfg);
    const { failures } = nakie.Nakie.evaluate({ config: cfg });
    if (failures.length) throw new Error(`Missing keys: ${failures.map(f => f.label).join(', ')}`);
  });

  info.register('root cause analysis example', async () => {
    const rc = nakie.Nakie.rootCause((traces) => {
      // Very simple demo: ensure a trace with label exists
      const has = traces.some(t => t.label === 'config-loaded');
      return has ? null : { reason: 'no-config-trace' };
    });
    if (rc) throw new Error(`Root cause found: ${JSON.stringify(rc)}`);
  });
};
