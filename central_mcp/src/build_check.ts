
import fs from 'fs';
import path from 'path';
/**
 * Ensures the dist directory exists. 
 * The Python Orchestrator relies on this path.
 */
const distPath = path.resolve(process.cwd(), 'dist');

if (!fs.existsSync(distPath)) {
    console.error("🔴 Build Error: dist/ directory missing. Run 'npm run build'.");
    process.exit(1);
}

if (!fs.existsSync(path.join(distPath, 'server.js'))) {
    console.error("🔴 Build Error: dist/server.js not found.");
    process.exit(1);
}

console.log("✅ MCP Server build validated for Python Orchestrator.");