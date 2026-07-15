# SmartHub Central MCP

The central MCP server exposes the user-facing operations from `openapi.json` as
tools for the SmartHub VS Code extension. It forwards each tool call to the
FastAPI backend and preserves the backend JWT supplied by the extension.

## Setup

```powershell
npm install
npm run build
npm start
```

Configuration:

- `BACKEND_URL`: FastAPI base URL, default `http://localhost:8000`
- `BACKEND_TIMEOUT_MS`: backend request timeout, default `120000`

Authentication tokens are sent per tool call by the extension. Do not put user
tokens in `.env`.
