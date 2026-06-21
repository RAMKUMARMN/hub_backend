import * as fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

import type { ToolDefinition } from "./types/tool.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export function getTools(): ToolDefinition[] {
  const registryPath = path.join(
    __dirname,
    "registries",
    "toolRegistry.json"
  );

  const content = fs.readFileSync(
    registryPath,
    "utf8"
  );

  return JSON.parse(content) as ToolDefinition[];
}