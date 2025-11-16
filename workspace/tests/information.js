// tests/information.js
'use strict';

const path = require('path');
const fs = require('fs');
const vm = require('vm');

class Information {
  constructor(options = {}) {
    const {
      rootDir = path.resolve(__dirname, '..'),
      testsDir = __dirname,
      workieDir = path.join(__dirname, '.workie'),
      nakieDir = path.join(__dirname, '.nakie'),
      shadowDir = path.join(__dirname, 'sandbox', 'shadow-root', 'x-dependencies'),
      logger = console,

      contexty = {}
    } = options;

    this.paths = { rootDir, testsDir, workieDir, nakieDir, shadowDir };
    this.logger = logger;

    this.contexty = {}

    this._registered = [];
    this._workieCache = new Map();
    this._nakieCache = new Map();

    // Ensure shadow dir exists
    fs.mkdirSync(this.paths.shadowDir, { recursive: true });
  }

  // Register a test step (name + async fn)
  register(name, fn) {
    if (typeof fn !== 'function') throw new Error(`register("${name}") requires a function`);
    this._registered.push({ name, fn });
  }

  // Strict require: only allow .workie files (and JSON) through a minimal loader
  require(relPath) {
    if (relPath === ('rarovery-api')) {
      return this.contexty
    }
    
    const fullPath = path.resolve(this.paths.workieDir, relPath);
    if (!fullPath.startsWith(this.paths.workieDir)) {
      throw new Error(`Blocked require: ${relPath} is outside .workie`);
    }
    if (this._workieCache.has(fullPath)) return this._workieCache.get(fullPath);

    const ext = path.extname(fullPath);
    if (!fs.existsSync(fullPath)) {
      throw new Error(`Workie module not found: ${relPath}`);
    }

    let exported;
    if (ext === '.js') {
      const code = fs.readFileSync(fullPath, 'utf8');

      // build a normal require that resolves relative to .workie
      const safeRequire = (mod) => {
        // allow Node builtins
        if (require('module').builtinModules.includes(mod)) {
          return require(mod);
        }

        // allow relative imports only inside .workie
        if (mod.startsWith('.') || path.isAbsolute(mod)) {
          const target = path.resolve(path.dirname(fullPath), mod);
          if (!target.startsWith(this.paths.workieDir)) {
            throw new Error(`Blocked require: ${mod} is outside .workie`);
          }
          return this.require(path.relative(this.paths.workieDir, target));
        }

        throw new Error(`Blocked require: external module "${mod}"`);
      };

      const sandbox = {
        module: { exports: {} },
        exports: {},
        console: this.logger,
        require: safeRequire,
        __dirname: path.dirname(fullPath),
        __filename: fullPath,
      };

      vm.createContext(sandbox, { name: `workie:${relPath}` });
      const script = new vm.Script(code, { filename: fullPath });
      script.runInContext(sandbox);

      exported = sandbox.module.exports || sandbox.exports;
    } else if (ext === '.json') {
      const raw = fs.readFileSync(fullPath, 'utf8');
      exported = JSON.parse(raw);
    } else {
      // For non-JS deps, return a path handle under .workie
      exported = { path: fullPath };
    }

    this._workieCache.set(fullPath, exported);
    return exported;
  }

  // Expectation loader: runs a nakie file in a restricted context
  // name => loads .nakie/<name>.nakie.js
  expect(name, opts = {}) {
    const file = path.resolve(this.paths.nakieDir, `${name}.nakie.js`);
    if (!file.startsWith(this.paths.nakieDir)) {
      throw new Error(`Blocked expect: ${name} outside .nakie`);
    }
    if (!fs.existsSync(file)) {
      throw new Error(`Nakie file not found: ${name}`);
    }
    if (this._nakieCache.has(file)) return this._nakieCache.get(file);

    // Prepare a restricted fs that only sees shadowDir
    const shadowRoot = this.paths.shadowDir;
    const safeJoin = (p) => {
      const resolved = path.resolve(shadowRoot, p);
      if (!resolved.startsWith(shadowRoot)) {
        throw new Error(`Sandbox FS escape attempt: ${p}`);
      }
      return resolved;
    };

    const sfs = {
      readFileSync: (p, enc = 'utf8') => fs.readFileSync(safeJoin(p), enc),
      existsSync: (p) => fs.existsSync(safeJoin(p)),
      readdirSync: (p) => fs.readdirSync(safeJoin(p)),
      statSync: (p) => fs.statSync(safeJoin(p)),
      // If you need more, add carefully.
    };

    const contextAPI = {
      console: this.logger,
      // Provide a minimal API surface to define expectations
      Nakie: createNakieAPI({ sfs, info: this, options: opts }),
      module: { exports: {} },
      exports: {},
    };

    vm.createContext(contextAPI, { name: `nakie:${name}` });
    const code = fs.readFileSync(file, 'utf8');
    const script = new vm.Script(code, { filename: file });
    script.runInContext(contextAPI);

    const exported = contextAPI.module.exports || contextAPI.exports;
    this._nakieCache.set(file, exported);
    return exported;
  }

  // Execute all registered steps; returns a summary
  async execute({ bail = false } = {}) {
    const results = [];
    for (const { name, fn } of this._registered) {
      const start = Date.now();
      try {
        await Promise.resolve(fn());
        results.push({ name, status: 'passed', durationMs: Date.now() - start });
        this.logger.log(`✓ ${name}`);
      } catch (err) {
        results.push({
          name,
          status: 'failed',
          error: { message: err.message, stack: err.stack },
          durationMs: Date.now() - start
        });
        this.logger.error(`✗ ${name}: ${err.message}`);
        if (bail) break;
      }
    }
    return {
      total: results.length,
      passed: results.filter(r => r.status === 'passed').length,
      failed: results.filter(r => r.status === 'failed').length,
      results
    };
  }

  // Utility: populate shadow sandbox with whitelisted files from src/static
  // Call this from index.js before nakie execution.
  static materializeShadow({ srcDir, staticDir, shadowDir, whitelist = [] }) {
    fs.mkdirSync(shadowDir, { recursive: true });
    for (const entry of whitelist) {
      // entry: { from: 'src/foo.py', to: 'src/foo.py' } relative to their roots
      const [root, rel] = entry.from.startsWith('src/')
        ? [srcDir, entry.from.slice(4)]
        : entry.from.startsWith('static/')
          ? [staticDir, entry.from.slice(7)]
          : [null, null];

      if (!root) throw new Error(`Invalid whitelist entry: ${entry.from}`);
      const srcPath = path.resolve(root, rel);
      const destPath = path.resolve(shadowDir, entry.to || entry.from);
      const destDir = path.dirname(destPath);
      fs.mkdirSync(destDir, { recursive: true });
      fs.copyFileSync(srcPath, destPath);
    }
  }

  static cleanup({ srcDir, staticDir, shadowDir, whitelist = [] }) {
    const dirsToDelete = []
    for (const entry of whitelist) {
      // entry: { from: 'src/foo.py', to: 'src/foo.py' } relative to their roots
      const [root, rel] = entry.from.startsWith('src/')
        ? [srcDir, entry.from.slice(4)]
        : entry.from.startsWith('static/')
          ? [staticDir, entry.from.slice(7)]
          : [null, null];

      if (!root) throw new Error(`Invalid whitelist entry: ${entry.from}`);
      const destPath = path.resolve(shadowDir, entry.to || entry.from);
      const destDir = path.dirname(destPath);
      fs.rmSync(destPath);
      
      try {
        fs.rmdirSync(destDir);
      } catch (e) {
        if (e.code === 'ENOTEMPTY') {
          if (dirsToDelete.includes(destDir)) return;
          dirsToDelete.push(destDir)
        }
      }
    }

    console.log(dirsToDelete)
    if (dirsToDelete.length !== 0) dirsToDelete.forEach((dir) => fs.rmdirSync(dir))
  }
}

function createNakieAPI({ sfs, info, options }) {
  // Nakie API: define rules, trace steps, and root cause analysis helpers.
  const rules = [];
  const traces = [];

  return {
    defineRule(label, predicate) {
      if (typeof predicate !== 'function') throw new Error('predicate must be a function');
      rules.push({ label, predicate });
    },
    trace(label, payload) {
      traces.push({ label, payload, ts: Date.now() });
    },
    evaluate(context) {
      const failures = [];
      for (const r of rules) {
        let ok = false;
        try {
          ok = !!r.predicate(context, { sfs, trace: this.trace });
        } catch (e) {
          failures.push({ label: r.label, error: e.message });
          continue;
        }
        if (!ok) failures.push({ label: r.label });
      }
      return { failures, traces };
    },
    // Example: help diagnose root cause by scanning traces
    rootCause(analyzer) {
      if (typeof analyzer !== 'function') return null;
      try {
        return analyzer(traces, { sfs, options });
      } catch (e) {
        return { error: e.message };
      }
    },
    // Access Information if needed (read-only public surface)
    information() {
      return {
        require: info.require.bind(info),
        register: info.register.bind(info),
        expect: info.expect.bind(info),
      };
    }
  };
}

module.exports = { Information };


