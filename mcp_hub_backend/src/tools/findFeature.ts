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

  const features = new Set<string>();

  const searchDirectory = (
    dir: string,
    depth: number = 0
  ) => {

    if (depth > 5) {
      return;
    }

    try {

      const files =
        fs.readdirSync(dir);

      for (const file of files) {

        const fullPath =
          path.join(dir, file);

        const stat =
          fs.statSync(fullPath);

        //
        // Skip hidden folders
        //

        if (
          file.startsWith(".")
        ) {
          continue;
        }

        //
        // Skip __pycache__
        //

        if (
          file === "__pycache__"
        ) {
          continue;
        }

        if (
          stat.isDirectory()
        ) {

          if (
            file
              .toLowerCase()
              .includes(
                feature.toLowerCase()
              )
          ) {

            features.add(
              path.relative(
                HUB_BACKEND_PATH,
                fullPath
              )
            );
          }

          searchDirectory(
            fullPath,
            depth + 1
          );

          continue;
        }

        //
        // Skip .pyc files
        //

        if (
          file.endsWith(".pyc")
        ) {
          continue;
        }

        if (
          stat.isFile()
        ) {

          if (
            file
              .toLowerCase()
              .includes(
                feature.toLowerCase()
              )
          ) {

            features.add(
              path.relative(
                HUB_BACKEND_PATH,
                fullPath
              )
            );
          }
        }
      }

    } catch {

      // ignore unreadable folders

    }
  };

  searchDirectory(root);

  const locations =
    Array.from(features)
      .sort();

  return {

    content: [

      {

        type:
          "text" as const,

        text:
          JSON.stringify(
            {
              feature,
              found:
                locations.length > 0,
              locations,
            },
            null,
            2
          ),
      },
    ],
  };
}