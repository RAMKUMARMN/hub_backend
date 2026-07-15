import { SmartHubSkill } from '../../types/index.js';
import { forwardToBackend } from '../../core/api_client.js';
import {
  createJsonSkill,
  createUploadSkill,
  errorResult,
  idProperty,
  jsonResult,
  stringProperty,
  withoutUndefined,
} from './skill_helpers.js';

const todoFields = {
  title: stringProperty('Todo title.'),
  description: stringProperty('Optional details.'),
  due_date: stringProperty('ISO 8601 due date and time.', 'date-time'),
  priority: { type: 'string', enum: ['low', 'medium', 'high'] },
  reminder_at: stringProperty('ISO 8601 reminder date and time.', 'date-time'),
};

const pollFields = Object.fromEntries([
  'q1_modules_count', 'q2_overall_progress', 'q3_ready_independent', 'q4_need_1on1',
  'q6_daily_hours', 'q7_meeting_goals', 'q8_internship_rating',
  'q9_tech_stack_comfort', 'q10_docs_rating', 'q12_overall_feeling',
  'q13_open_feedback',
].map(name => [name, { type: 'string' }]));

export const apiSkills: SmartHubSkill[] = [
  createJsonSkill({
    name: 'health_check',
    description: 'Check whether the SmartHub backend is reachable.',
    method: 'GET',
    endpoint: '/api/v1/health',
    requiresAuth: false,
  }),
  createJsonSkill({
    name: 'get_my_profile',
    description: 'Get the authenticated user profile.',
    method: 'GET',
    endpoint: '/api/v1/auth/me',
  }),
  createJsonSkill({
    name: 'update_my_profile',
    description: 'Update the authenticated user profile.',
    method: 'PUT',
    endpoint: '/api/v1/auth/profile',
    schema: {
      type: 'object',
      properties: {
        full_name: stringProperty('Full name.'),
        phone: stringProperty('Phone number.'),
        device_token: stringProperty('Push notification device token.'),
      },
      additionalProperties: false,
    },
    body: args => withoutUndefined(args, ['full_name', 'phone', 'device_token']),
  }),
  createUploadSkill({
    name: 'upload_my_avatar',
    description: 'Upload an image file as the authenticated user avatar.',
    endpoint: '/api/v1/auth/avatar',
  }),
  createJsonSkill({
    name: 'request_email_verification',
    description: 'Send an email verification OTP.',
    method: 'POST',
    endpoint: '/api/v1/auth/email_verification',
    requiresAuth: false,
    schema: {
      type: 'object',
      properties: { email: stringProperty('Account email.', 'email') },
      required: ['email'],
      additionalProperties: false,
    },
    body: args => ({ email: args.email }),
  }),
  createJsonSkill({
    name: 'verify_email_otp',
    description: 'Verify an email address using its OTP.',
    method: 'POST',
    endpoint: '/api/v1/auth/verify-email-otp',
    requiresAuth: false,
    schema: {
      type: 'object',
      properties: {
        email: stringProperty('Account email.', 'email'),
        otp: stringProperty('Email OTP code.'),
      },
      required: ['email', 'otp'],
      additionalProperties: false,
    },
    body: args => ({ email: args.email, otp: args.otp }),
  }),
  createJsonSkill({
    name: 'list_chat_sessions',
    description: 'List the current user chat sessions, newest first.',
    method: 'GET',
    endpoint: '/api/v1/chat/sessions',
  }),
  createJsonSkill({
    name: 'create_chat_session',
    description: 'Create a chat session.',
    method: 'POST',
    endpoint: '/api/v1/chat/sessions',
    schema: {
      type: 'object',
      properties: { title: stringProperty('Session title. Defaults to New Chat.') },
      additionalProperties: false,
    },
    body: args => ({ title: args.title || 'New Chat' }),
  }),
  createJsonSkill({
    name: 'rename_chat_session',
    description: 'Rename a chat session using its UUID.',
    method: 'PATCH',
    endpoint: args => `/api/v1/chat/sessions/${encodeURIComponent(args.session_id)}`,
    schema: {
      type: 'object',
      properties: { session_id: idProperty('session'), title: stringProperty('New session title.') },
      required: ['session_id', 'title'],
      additionalProperties: false,
    },
    body: args => ({ title: args.title }),
  }),
  createJsonSkill({
    name: 'delete_chat_session',
    description: 'Permanently delete a chat session using its UUID.',
    method: 'DELETE',
    endpoint: args => `/api/v1/chat/sessions/${encodeURIComponent(args.session_id)}`,
    schema: {
      type: 'object',
      properties: { session_id: idProperty('session') },
      required: ['session_id'],
      additionalProperties: false,
    },
  }),
  createJsonSkill({
    name: 'get_chat_messages',
    description: 'Get all messages in a chat session.',
    method: 'GET',
    endpoint: args => `/api/v1/chat/sessions/${encodeURIComponent(args.session_id)}/messages`,
    schema: {
      type: 'object',
      properties: { session_id: idProperty('session') },
      required: ['session_id'],
      additionalProperties: false,
    },
  }),
  createJsonSkill({
    name: 'send_chat_message',
    description: 'Send a message to a backend chat session. Enable use_rag for questions about uploaded documents.',
    method: 'POST',
    endpoint: args => `/api/v1/chat/sessions/${encodeURIComponent(args.session_id)}/messages`,
    schema: {
      type: 'object',
      properties: {
        session_id: idProperty('session'),
        content: stringProperty('Message to send.'),
        use_rag: { type: 'boolean', description: 'Use uploaded documents as context.' },
      },
      required: ['session_id', 'content'],
      additionalProperties: false,
    },
    body: args => ({ content: args.content, use_rag: args.use_rag ?? false }),
  }),
  createUploadSkill({
    name: 'upload_document',
    description: 'Upload a PDF, DOCX, TXT, PNG, or JPEG document from an absolute local path.',
    endpoint: '/api/v1/documents/upload',
  }),
  createJsonSkill({
    name: 'list_documents',
    description: 'List documents already uploaded to RAG, newest first. Do not upload these files again.',
    method: 'GET',
    endpoint: '/api/v1/documents/',
  }),
  {
    name: 'summarize_latest_document',
    description: 'Select the latest already-uploaded document, create or reuse a chat session, and summarize it with RAG. Use this for requests mentioning the latest or most recent document; do not call upload_document.',
    requiresAuth: true,
    schema: {
      type: 'object',
      properties: {
        instruction: stringProperty('Optional user instructions for the summary.'),
      },
      additionalProperties: false,
    },
    execute: async (args, context) => {
      try {
        const documents = await forwardToBackend('GET', '/api/v1/documents/', {
          baseUrl: context.backendUrl,
          token: context.token,
        });
        if (!Array.isArray(documents) || documents.length === 0) {
          return jsonResult({
            found: false,
            message: 'No uploaded documents are available.',
          });
        }

        const latest = [...documents].sort((left: any, right: any) =>
          new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
        )[0];
        if (!latest.processed) {
          return jsonResult({
            found: true,
            ready: false,
            document: latest,
            message: 'The latest document is still being processed. Try again shortly.',
          });
        }

        const sessions = await forwardToBackend('GET', '/api/v1/chat/sessions', {
          baseUrl: context.backendUrl,
          token: context.token,
        });
        const session = Array.isArray(sessions) && sessions.length > 0
          ? sessions[0]
          : await forwardToBackend('POST', '/api/v1/chat/sessions', {
            baseUrl: context.backendUrl,
            token: context.token,
            body: { title: `Summary: ${latest.filename}` },
          });

        const instruction = args.instruction?.trim() ||
          `Summarize the uploaded document named "${latest.filename}". ` +
          'Give the main points, important details, and a concise conclusion. ' +
          'Use the document content retrieved through RAG.';
        const summary = await forwardToBackend(
          'POST',
          `/api/v1/chat/sessions/${encodeURIComponent(session.id)}/messages`,
          {
            baseUrl: context.backendUrl,
            token: context.token,
            body: { content: instruction, use_rag: true },
          },
        );

        return jsonResult({
          found: true,
          ready: true,
          document: {
            id: latest.id,
            filename: latest.filename,
            created_at: latest.created_at,
          },
          session_id: session.id,
          summary: summary.response || summary,
        });
      } catch (error) {
        return errorResult(error);
      }
    },
  },
  createJsonSkill({
    name: 'delete_document',
    description: 'Permanently delete an uploaded document using its UUID.',
    method: 'DELETE',
    endpoint: args => `/api/v1/documents/${encodeURIComponent(args.document_id)}`,
    schema: {
      type: 'object',
      properties: { document_id: idProperty('document') },
      required: ['document_id'],
      additionalProperties: false,
    },
  }),
  createJsonSkill({
    name: 'list_todos',
    description: 'List todos. Optionally filter by completed status.',
    method: 'GET',
    endpoint: '/api/v1/todos/',
    schema: {
      type: 'object',
      properties: { completed: { type: 'boolean' } },
      additionalProperties: false,
    },
    query: args => args.completed === undefined ? {} : { completed: args.completed },
  }),
  createJsonSkill({
    name: 'create_todo',
    description: 'Create a todo. Convert natural-language dates to ISO 8601.',
    method: 'POST',
    endpoint: '/api/v1/todos/',
    schema: {
      type: 'object',
      properties: todoFields,
      required: ['title'],
      additionalProperties: false,
    },
    body: args => withoutUndefined(args, Object.keys(todoFields)),
  }),
  createJsonSkill({
    name: 'update_todo',
    description: 'Update one or more fields of a todo using its UUID.',
    method: 'PATCH',
    endpoint: args => `/api/v1/todos/${encodeURIComponent(args.todo_id)}`,
    schema: {
      type: 'object',
      properties: { todo_id: idProperty('todo'), ...todoFields },
      required: ['todo_id'],
      additionalProperties: false,
    },
    body: args => withoutUndefined(args, Object.keys(todoFields)),
  }),
  createJsonSkill({
    name: 'set_todo_completion',
    description: 'Mark a todo completed or incomplete.',
    method: 'PATCH',
    endpoint: args => `/api/v1/todos/${encodeURIComponent(args.todo_id)}/complete`,
    schema: {
      type: 'object',
      properties: { todo_id: idProperty('todo'), completed: { type: 'boolean' } },
      required: ['todo_id', 'completed'],
      additionalProperties: false,
    },
    body: args => ({ completed: args.completed }),
  }),
  createJsonSkill({
    name: 'delete_todo',
    description: 'Permanently delete a todo using its UUID.',
    method: 'DELETE',
    endpoint: args => `/api/v1/todos/${encodeURIComponent(args.todo_id)}`,
    schema: {
      type: 'object',
      properties: { todo_id: idProperty('todo') },
      required: ['todo_id'],
      additionalProperties: false,
    },
  }),
  createJsonSkill({
    name: 'submit_poll',
    description: 'Submit an anonymous internship pulse-check response.',
    method: 'POST',
    endpoint: '/api/v1/poll/submit',
    requiresAuth: false,
    schema: {
      type: 'object',
      properties: {
        ...pollFields,
        q5_biggest_challenges: { type: 'array', items: { type: 'string' } },
        q11_improvements: { type: 'array', items: { type: 'string' } },
      },
      additionalProperties: false,
    },
    body: args => args,
  }),
  createJsonSkill({
    name: 'get_poll_results',
    description: 'Get aggregated poll results. Admin access is required.',
    method: 'GET',
    endpoint: '/api/v1/poll/results',
  }),
  createJsonSkill({
    name: 'list_poll_responses',
    description: 'List raw poll responses. Admin access is required.',
    method: 'GET',
    endpoint: '/api/v1/poll/responses',
  }),
  createJsonSkill({
    name: 'list_users',
    description: 'List system users. Admin access is required.',
    method: 'GET',
    endpoint: '/api/v1/admin/users',
  }),
  createJsonSkill({
    name: 'delete_user',
    description: 'Permanently delete a user. Admin access is required.',
    method: 'DELETE',
    endpoint: args => `/api/v1/admin/users/${encodeURIComponent(args.user_id)}`,
    schema: {
      type: 'object',
      properties: { user_id: idProperty('user') },
      required: ['user_id'],
      additionalProperties: false,
    },
  }),
  createUploadSkill({
    name: 'bulk_create_users',
    description: 'Upload a CSV file to create users in bulk. Admin access is required.',
    endpoint: '/api/v1/admin/users/bulk',
  }),
  createJsonSkill({
    name: 'run_n8n_task',
    description: 'Send a message and task name to the backend n8n integration.',
    method: 'POST',
    endpoint: '/api/v1/n8n-test/',
    schema: {
      type: 'object',
      properties: {
        message: stringProperty('Message or payload for the workflow.'),
        task: stringProperty('Backend task name.'),
      },
      required: ['message', 'task'],
      additionalProperties: false,
    },
    body: args => ({ message: args.message, task: args.task }),
  }),
  createJsonSkill({
    name: 'summarize_document_text',
    description: 'Run the document-summary workflow for supplied text and an email address.',
    method: 'POST',
    endpoint: '/api/v1/workflows/document-summary',
    schema: {
      type: 'object',
      properties: {
        document_text: stringProperty('Document text to summarize.'),
        email: stringProperty('User email for workflow context.', 'email'),
      },
      required: ['document_text', 'email'],
      additionalProperties: false,
    },
    body: args => ({ document_text: args.document_text, email: args.email }),
  }),
  createJsonSkill({
    name: 'get_notifications',
    description: 'List notifications for the current user.',
    method: 'GET',
    endpoint: '/api/v1/notifications/',
  }),
  createJsonSkill({
    name: 'get_unread_notification_count',
    description: 'Get the number of unread notifications.',
    method: 'GET',
    endpoint: '/api/v1/notifications/unread-count',
  }),
  createJsonSkill({
    name: 'mark_notification_read',
    description: 'Mark a notification as read using its numeric ID.',
    method: 'PATCH',
    endpoint: args => `/api/v1/notifications/${encodeURIComponent(args.notification_id)}/read`,
    schema: {
      type: 'object',
      properties: { notification_id: { type: 'integer', description: 'Notification ID.' } },
      required: ['notification_id'],
      additionalProperties: false,
    },
  }),
  createJsonSkill({
    name: 'run_notification_reminders',
    description: 'Run pending reminder notifications. Elevated access may be required.',
    method: 'POST',
    endpoint: '/api/v1/notifications/run-reminders',
  }),
  createJsonSkill({
    name: 'send_test_push_notification',
    description: 'Send a test push notification to the current user.',
    method: 'POST',
    endpoint: '/api/v1/notifications/test-push',
  }),
  createJsonSkill({
    name: 'send_test_email_notification',
    description: 'Send a test email notification to the current user.',
    method: 'POST',
    endpoint: '/api/v1/notifications/test-email',
  }),
];

export const avatarEndpointSkill: SmartHubSkill = {
  name: 'get_avatar_endpoint',
  description: 'Get the backend avatar URL for a user ID.',
  requiresAuth: false,
  schema: {
    type: 'object',
    properties: { user_id: idProperty('user') },
    required: ['user_id'],
    additionalProperties: false,
  },
  execute: async (args, context) => jsonResult({
    url: `${context.backendUrl.replace(/\/$/, '')}/api/v1/auth/avatar/${encodeURIComponent(args.user_id)}`,
  }),
};
