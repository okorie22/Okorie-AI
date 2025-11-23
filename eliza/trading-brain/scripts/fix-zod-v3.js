const fs = require('fs');
const path = require('path');

function fixZod(dir) {
  const zodPath = path.join(dir, 'zod');
  if (!fs.existsSync(zodPath) || !fs.existsSync(path.join(zodPath, 'lib'))) {
    return;
  }

  // Create v3 files
  const v3js = path.join(zodPath, 'v3.js');
  const v3mjs = path.join(zodPath, 'v3.mjs');
  const v3dts = path.join(zodPath, 'v3.d.ts');
  
  if (!fs.existsSync(v3js)) {
    fs.writeFileSync(v3js, 'module.exports=require("./lib/index.js");');
  }
  if (!fs.existsSync(v3mjs)) {
    fs.writeFileSync(v3mjs, 'export * from "./lib/index.js";');
  }
  if (!fs.existsSync(v3dts)) {
    fs.writeFileSync(v3dts, 'export * from "./lib/index";');
  }

  // Update package.json exports
  const pkgPath = path.join(zodPath, 'package.json');
  if (fs.existsSync(pkgPath)) {
    try {
      const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
      if (!pkg.exports) {
        pkg.exports = {};
      }
      if (!pkg.exports['./v3']) {
        pkg.exports['./v3'] = {
          'import': './v3.mjs',
          'require': './v3.js',
          'types': './v3.d.ts'
        };
        fs.writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + '\n');
      }
    } catch (e) {
      // Ignore errors
    }
  }
}

function walkDir(dir, depth = 0) {
  if (depth > 10) return;
  
  try {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name === 'zod') {
          fixZod(dir);
        } else if (entry.name === 'node_modules' || depth === 0) {
          walkDir(fullPath, entry.name === 'node_modules' ? 0 : depth + 1);
        }
      }
    }
  } catch (e) {
    // Ignore errors
  }
}

walkDir('node_modules', 0);
console.log('Fixed all zod v3 exports');

