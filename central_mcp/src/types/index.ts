export interface JsonObjectSchema {
    type: 'object';
    properties: Record<string, unknown>;
    required?: string[];
    additionalProperties?: boolean;
}

export interface SkillContext {
    backendUrl: string;
    token?: string;
}

export interface SmartHubSkill {
    name: string;
    description: string;
    requiresAuth?: boolean;
    schema: JsonObjectSchema;
    execute: (args: Record<string, any>, context: SkillContext) => Promise<SmartHubSkillResult>;
}

export interface SmartHubSkillResult {
    content: Array<{
        type: 'text';
        text: string;
    }>;
    isError?: boolean;
}
