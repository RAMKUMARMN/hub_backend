import * as fs from "fs";
import path from "path";
import { HUB_BACKEND_PATH } from "../config.js";

export async function findFeatureHandler({
  feature,
}: {
  feature: string;
}) {
  const root = path.join(
    HUB_BACKEND_PATH,
    "app"
  );

  const features: string[] = [];

  const searchDirectory = (dir: string, depth: number = 0) => {
    if (depth > 5) return;

    try {
      const files = fs.readdirSync(dir);

      for (const file of files) {
        const fullPath = path.join(dir, file);
        const stat = fs.statSync(fullPath);

        if (stat.isDirectory() && !file.startsWith(".")) {
          if (file.toLowerCase().includes(feature.toLowerCase())) {
            features.push(path.relative(HUB_BACKEND_PATH, fullPath));
          }
          searchDirectory(fullPath, depth + 1);
        } else if (stat.isFile()) {
          if (file.toLowerCase().includes(feature.toLowerCase())) {
            features.push(path.relative(HUB_BACKEND_PATH, fullPath));
          }
        }
      }
    } catch (error) {
      // Handle cases where directory cannot be read
    }
  };

  searchDirectory(root);

  return {
    content: [
      {
        type: "text" as const,
        text: JSON.stringify(
          {
            feature,
            found: features.length > 0,
            locations: features,
          },
          null,
          2
        ),
      },
    ],
  };
}
