/**
 * lifecycle_rules.ts
 * Defines the handshake and capability announcement for the Python Orchestrator.
 * This ensures the Python ai_router can dynamically register these tools.
 */

export interface MCPCapability {
    name: string;
    version: string;
    capabilities: {
        tools: {
            listChanged?: boolean;
        };
    };
}

export const serverLifecycleDefinition: MCPCapability = {
    name: "smarthub-central-mcp",
    version: "2.0.0",
    capabilities: {
        tools: {
            listChanged: true // Tells the orchestrator tools are dynamic
        }
    }
};

/**
 * Hook to provide initial context upon connection.
 */
export const getInitialContext = () => {
    return {
        description: "Centralized MCP Bridge for SmartHub 2.0. Handles RAG, Todos, Admin, and Chat.",
        status: "READY"
    };
};