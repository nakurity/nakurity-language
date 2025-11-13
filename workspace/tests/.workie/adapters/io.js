// tests/.workie/adapters/io.js
'use strict';

// Minimal adapter that could wrap non-JS deps (e.g., config files)
// Keep it pure; no Node globals except what Information exposes when required.

function normalizeEndpoint(ep) {
  if (typeof ep !== 'string') return '';
  return ep.trim().replace(/\/+$/, '');
}

module.exports = { normalizeEndpoint };
