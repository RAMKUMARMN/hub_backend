import * as fs from "fs";
import path from "path";
import { HUB_BACKEND_PATH } from "../config.js";

export async function discoverModelsHandler() {
  const modelsDir = path.join(
    HUB_BACKEND_PATH,
    "app",
    "models"
  );

  const models = fs
    .readdirSync(modelsDir)
    .filter(
      (file) =>
        file.endsWith(".py") &&
        file !== "__init__.py"
    );

  return {
    content: [
      {
        type: "text" as const,
        text: JSON.stringify(models, null, 2),
      },
    ],
  };
}