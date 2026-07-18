import * as fs from "fs";
import path from "path";
import { HUB_BACKEND_PATH } from "../config.js";

export async function discoverDatabaseConfigHandler() {
  return {
    content: [
      {
        type: "text" as const,
        text: JSON.stringify(
          {
            database: "database.py",
            migrations: "alembic/",
            configuration: "config.py",
          },
          null,
          2
        ),
      },
    ],
  };
}
