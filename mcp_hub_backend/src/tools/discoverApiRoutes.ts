import * as fs from "fs";
import path from "path";
import { HUB_BACKEND_PATH } from "../config.js";

export async function discoverApiRoutesHandler() {
  const routesDir = path.join(
    HUB_BACKEND_PATH,
    "app",
    "routers"
  );

  const routes = fs
    .readdirSync(routesDir)
    .filter(
      (file) =>
        file.endsWith(".py") &&
        file !== "__init__.py"
    );

  return {
    content: [
      {
        type: "text" as const,
        text: JSON.stringify(routes, null, 2),
      },
    ],
  };
}