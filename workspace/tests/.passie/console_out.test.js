// tests/.passie/console_printing.test.js
'use strict';

module.exports = function (info) {
  // Use sandboxed workie resource (e.g., JSON config or helper adapter)
  const cfg = info.require('adapters/hello-world-masha.js');

  // Load nakie expectations
  const nakie = info.expect('nakie_api', { mode: 'strict' });

  // Register test steps
  info.register('should print hello world', async () => {
    info.require('masha-files/hello-world.masha');
    if (cfg.output === undefined) {
      throw new Error('Nakurity Lang failed at the language level, see error above ^^')
    }
    
    if (!cfg.ok) {
      throw new Error(`Nakurity Lang did not print hello world. Got:\n${cfg.output}`);
    }
  });
};
