// tests/.nakie/example.nakie.js
'use strict';

// Export nothing; we rely on the Nakie API in the context.
// You can still set module.exports if you want to pass utilities back.

module.exports = {
  // Optional helpers for tests can be exported
  Nakie
};

Nakie.defineRule('has-api-key', (ctx) => {
  return ctx.config && typeof ctx.config.apiKey === 'string' && ctx.config.apiKey.length > 0;
});

Nakie.defineRule('has-endpoint', (ctx) => {
  return ctx.config && typeof ctx.config.endpoint === 'string' && ctx.config.endpoint.startsWith('http');
});

// Access sandboxed files (mirror of src/static) via sfs inside predicate if needed.
// Example:
// Nakie.defineRule('runtime-exists', (ctx, { sfs }) => sfs.existsSync('src/runtime.py'));
