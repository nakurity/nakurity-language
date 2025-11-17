// tests/.passie/runnie.test.js
'use strict';

module.exports = function (info) {
  // Use sandboxed workie resource (e.g., JSON config or helper adapter)
  const cfg = info.require('helpers/someDep.json');

  // Load nakie expectations
  const nakie = info.expect('nakie_api', { mode: 'strict' });

  // Register test steps
};
