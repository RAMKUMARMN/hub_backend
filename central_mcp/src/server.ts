import 'dotenv/config';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';

import { skillRegistry } from './plugins/registry.js';
import { serverLifecycleDefinition } from './plugins/skills/lifecycle_rules.js';

const serverRegistry = new Map<string, Client>();

const server = new Server(
  {
    name: serverLifecycleDefinition.name,
    version: serverLifecycleDefinition.version,
  },
  {
    capabilities: serverLifecycleDefinition.capabilities,
  },
);

export async function registerSecondaryServer(name: string, serverPath: string) {
  const client = new Client(
    { name: `bridge-${name}`, version: '1.0.0' },
    { capabilities: {} },
  );
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [serverPath],
  });

  await client.connect(transport);
  serverRegistry.set(name, client);
  console.error(`Aggregated secondary MCP server: ${name}`);
}

server.setRequestHandler(ListToolsRequestSchema, async () => {
  const localTools = Object.values(skillRegistry).map(skill => ({
    name: skill.name,
    description: skill.description,
    inputSchema: skill.schema,
  }));

  const remoteTools: any[] = [];
  for (const client of serverRegistry.values()) {
    const result = await client.listTools();
    remoteTools.push(...result.tools);
  }

  return { tools: [...localTools, ...remoteTools] };
});

server.setRequestHandler(CallToolRequestSchema, async request => {
  const { name, arguments: rawArgs } = request.params;
  const skill = skillRegistry[name];

  if (skill) {
    const args = (rawArgs || {}) as Record<string, any>;
    const token = typeof args.token === 'string'
      ? args.token
      : typeof args._authToken === 'string'
        ? args._authToken
        : process.env.ADMIN_TOKEN;
    const backendUrl = typeof args.backendUrl === 'string'
      ? args.backendUrl
      : process.env.BACKEND_URL || 'http://localhost:8000';

    if (skill.requiresAuth && !token) {
      return {
        content: [{ type: 'text', text: 'Authentication required. Use @smarthub login first.' }],
        isError: true,
      };
    }

    try {
      const userArgs = { ...args };
      delete userArgs.token;
      delete userArgs._authToken;
      delete userArgs.backendUrl;

      const result = await skill.execute(userArgs, { token, backendUrl });
      if (!result || !Array.isArray(result.content)) {
        throw new Error(`Tool ${name} returned an invalid MCP result.`);
      }
      return {
        content: result.content,
        isError: result.isError || false,
      };
    } catch (error: any) {
      return {
        content: [{ type: 'text', text: `Tool ${name} failed: ${error.message}` }],
        isError: true,
      };
    }
  }

  for (const client of serverRegistry.values()) {
    try {
      return await client.callTool({ name, arguments: rawArgs as any });
    } catch {
      // Continue to the next registered secondary server.
    }
  }

  return {
    content: [{ type: 'text', text: `Tool not found: ${name}` }],
    isError: true,
  };
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('SmartHub Central MCP initialized via stdio.');
}

main().catch(error => {
  console.error('Fatal MCP initialization failure:', error);
  process.exit(1);
});
