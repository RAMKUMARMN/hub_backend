import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

// Tools
import { discoverBackendArchitectureHandler } from "./tools/discoverBackendArchitecture.js";
import { discoverApiRoutesHandler } from "./tools/discoverApiRoutes.js";
import { discoverModelsHandler } from "./tools/discoverModels.js";
import { discoverSchemasHandler } from "./tools/discoverSchemas.js";
import { discoverServicesHandler } from "./tools/discoverServices.js";
import { discoverDatabaseConfigHandler } from "./tools/discoverDatabaseConfig.js";
import { findFeatureHandler } from "./tools/findFeature.js";


const server = new McpServer({
  name: "hub-backend-mcp",
  version: "1.0.0",
});

// Backend architecture

server.tool(
  "discover_backend_architecture",
  "Discover the backend project architecture and folder structure",
  {},
  discoverBackendArchitectureHandler
);

// API routes

server.tool(
  "discover_api_routes",
  "Discover FastAPI router modules and API endpoints",
  {},
  discoverApiRoutesHandler
);

// Database models

server.tool(
  "discover_models",
  "Discover SQLAlchemy database models",
  {},
  discoverModelsHandler
);

// Request/response schemas

server.tool(
  "discover_schemas",
  "Discover API request and response schemas",
  {},
  discoverSchemasHandler
);

// Business services

server.tool(
  "discover_services",
  "Discover backend business logic services",
  {},
  discoverServicesHandler
);

// Database configuration

server.tool(
  "discover_database_config",
  "Discover database configuration and migration setup",
  {},
  discoverDatabaseConfigHandler
);

// Feature search

server.tool(
  "find_feature",
  "Find backend files related to a feature",
  {
    feature: z.string(),
  },
  findFeatureHandler
);

async function main() {
  const transport = new StdioServerTransport();

  await server.connect(transport);

  console.error("Hub Backend MCP Server Running...");
}

main().catch(console.error);