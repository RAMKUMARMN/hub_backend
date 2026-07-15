import { forwardToBackend, HttpMethod, uploadFileToBackend } from '../../core/api_client.js';
import { JsonObjectSchema, SkillContext, SmartHubSkill, SmartHubSkillResult } from '../../types/index.js';

type EndpointBuilder = string | ((args: Record<string, any>) => string);

interface JsonSkillOptions {
  name: string;
  description: string;
  schema?: JsonObjectSchema;
  method: HttpMethod;
  endpoint: EndpointBuilder;
  requiresAuth?: boolean;
  body?: (args: Record<string, any>) => unknown;
  query?: (args: Record<string, any>) => Record<string, unknown>;
}

export const emptySchema: JsonObjectSchema = {
  type: 'object',
  properties: {},
  additionalProperties: false,
};

export function jsonResult(data: unknown): SmartHubSkillResult {
  return {
    content: [{
      type: 'text',
      text: typeof data === 'string' ? data : JSON.stringify(data, null, 2),
    }],
  };
}

export function errorResult(error: unknown): SmartHubSkillResult {
  return {
    content: [{
      type: 'text',
      text: error instanceof Error ? error.message : String(error),
    }],
    isError: true,
  };
}

export function createJsonSkill(options: JsonSkillOptions): SmartHubSkill {
  return {
    name: options.name,
    description: options.description,
    schema: options.schema || emptySchema,
    requiresAuth: options.requiresAuth ?? true,
    execute: async (args, context) => {
      try {
        const endpoint = typeof options.endpoint === 'function'
          ? options.endpoint(args)
          : options.endpoint;
        const data = await forwardToBackend(options.method, endpoint, {
          baseUrl: context.backendUrl,
          token: context.token,
          body: options.body?.(args),
          query: options.query?.(args),
        });
        return jsonResult(data);
      } catch (error) {
        return errorResult(error);
      }
    },
  };
}

export function createUploadSkill(options: {
  name: string;
  description: string;
  endpoint: string;
  requiresAuth?: boolean;
}): SmartHubSkill {
  return {
    name: options.name,
    description: options.description,
    requiresAuth: options.requiresAuth ?? true,
    schema: {
      type: 'object',
      properties: {
        file_path: {
          type: 'string',
          description: 'Absolute path to the local file.',
        },
      },
      required: ['file_path'],
      additionalProperties: false,
    },
    execute: async (args, context: SkillContext) => {
      try {
        const data = await uploadFileToBackend(options.endpoint, args.file_path, {
          baseUrl: context.backendUrl,
          token: context.token,
        });
        return jsonResult(data);
      } catch (error) {
        return errorResult(error);
      }
    },
  };
}

export const stringProperty = (description: string, format?: string) => ({
  type: 'string',
  description,
  ...(format ? { format } : {}),
});

export const idProperty = (entity: string) => stringProperty(`Exact ${entity} UUID.`, 'uuid');

export function withoutUndefined(args: Record<string, any>, keys: string[]): Record<string, unknown> {
  return Object.fromEntries(keys.filter(key => args[key] !== undefined).map(key => [key, args[key]]));
}
