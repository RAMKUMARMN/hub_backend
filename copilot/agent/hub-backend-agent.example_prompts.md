## Example prompts for Hub Backend Agent

1) Implement a backend endpoint (plan + patch)

System: Use the Hub Backend Agent persona.
User: "Provide a 4-step plan to add an admin stats endpoint that returns counts for users, documents, and chat sessions. List files to change."

After approving the plan:
User: "Apply step 1 and return unified diffs/patches only."

2) Fix a frontend streaming bug

System: Use the Hub Backend Agent persona.
User: "Investigate `/chat/sessions/{id}/messages` SSE streaming issues: provide repro steps, a failing test in `tests/`, and a minimal fix. Start with a 3-step plan."

3) Prompt engineering helper

System: Use the Hub Backend Agent persona.
User: "Using the prompt-engineering skill, give me a system + user prompt pair to ask the assistant to implement a Next.js upload component that uses `useDocuments()` hook. Keep it under 120 words."

4) Test generation

System: Use the Hub Backend Agent persona.
User: "Provide a plan and patches to add unit tests for `src/hooks/useHubBackendHooks.ts` covering `uploadDocument` and error handling. Use `vitest` and mocking; propose dev-deps first."
