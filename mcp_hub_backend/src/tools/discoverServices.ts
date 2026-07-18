import * as fs from "fs";
import path from "path";
import { HUB_BACKEND_PATH } from "../config.js";

export async function discoverServicesHandler() {
  const servicesDir = path.join(
    HUB_BACKEND_PATH,
    "app",
    "services"
  );

  const services = fs
    .readdirSync(servicesDir)
    .filter(
      (file) =>
        file.endsWith(".py") &&
        file !== "__init__.py"
    );

  return {
    content: [
      {
        type: "text" as const,
        text: JSON.stringify(services, null, 2),
      },
    ],
  };
}