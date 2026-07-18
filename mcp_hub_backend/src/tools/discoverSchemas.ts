import * as fs from "fs";
import path from "path";
import { HUB_BACKEND_PATH } from "../config.js";

export async function discoverSchemasHandler() {
  const schemasDir = path.join(
    HUB_BACKEND_PATH,
    "app",
    "schemas"
  );

  const schemas = fs
    .readdirSync(schemasDir)
    .filter(
      (file) =>
        file.endsWith(".py") &&
        file !== "__init__.py"
    );

  return {
    content: [
      {
        type: "text" as const,
        text: JSON.stringify(schemas, null, 2),
      },
    ],
  };
}