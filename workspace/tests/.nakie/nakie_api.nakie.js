// tests/.nakie/nakie_api.nakie.js
'use strict';

// Export nothing; we rely on the Nakie API in the context.
// You can still set module.exports if you want to pass utilities back.

module.exports = {
  // Optional helpers for tests can be exported
  Nakie: Nakie
};

// Access sandboxed files (mirror of src/static) via sfs inside predicate if needed.
// Example:
// Nakie.defineRule('runtime-exists', (ctx, { sfs }) => sfs.existsSync('src/runtime.py'));
