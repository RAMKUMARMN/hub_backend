# RabbitMQ Notification Queue Specification

This document details the RabbitMQ publish-subscribe architecture and message pattern used to communicate between the `hub_backend` and the notification service.

## Queue Architecture

The messaging system is designed with a Direct Exchange model, containing three priority queues and a Dead Letter Association (DLA) queue for failed notifications.

### 1. Exchanges
- **`notification.exchange`**: The main direct exchange responsible for routing notifications to the appropriate priority queue based on the routing key (`high`, `medium`, or `low`).
- **`dla.exchange`**: The dead-letter exchange (DLX) that receives messages rejected or failed by consumers of the priority queues.

### 2. Queues
- **`high`**: High-priority queue (e.g., OTPs, verification emails, password recovery/resets). Bound to `notification.exchange` with routing key `high`.
- **`medium`**: Medium-priority queue (e.g., direct messages, important system alerts, calendar/todo reminders). Bound to `notification.exchange` with routing key `medium`.
- **`low`**: Low-priority queue (e.g., bulk newsletters, marketing emails, non-urgent notifications). Bound to `notification.exchange` with routing key `low`.
- **`dla`**: Dead Letter Queue (DLQ) for failed/rejected messages. Bound to `dla.exchange` with routing key `dla`.

### Dead Letter Association (DLA) Configuration
Each of the three priority queues (`high`, `medium`, `low`) is configured with the following arguments:
- `x-dead-letter-exchange`: `"dla.exchange"`
- `x-dead-letter-routing-key`: `"dla"`

If a consumer rejects a message without requeueing, or if a message expires, RabbitMQ automatically routes the message to the `dla` queue.

---

## Message Pattern (Payload Schema)

Messages published to the queues are JSON-encoded objects containing the following attributes:

| Field | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `channel` | `string` | Yes | The channel over which to send the notification (`email`, `sms`, `push`, `whatsapp`). | `"email"` |
| `recipient` | `string` | Yes | Recipient identifier (email address, phone number, FCM device token). | `"student@tkmce.ac.in"` |
| `subject` | `string` | No | Subject of the notification (applicable for email). | `"CixioHub - Email Verification Code"` |
| `body` | `string` | Yes | Plain-text content of the notification. | `"Your verification code is: 123456"` |
| `html_body` | `string` | No | HTML formatted body content. | `"<p>Your verification code is: 123456</p>"` |
| `title` | `string` | No | Title of the notification (defaults to `subject` if not provided). | `"CixioHub"` |
| `message_type` | `string` | Yes | Classification of the message type (`otp`, `password_reset`, `general`). | `"otp"` |
| `priority` | `string` | Yes | Priority level of the message (`high`, `medium`, `low`). | `"high"` |
| `data` | `object` | No | Custom payload/metadata (useful for push notifications). | `{"click_action": "VERIFY"}` |

### JSON Payload Example (OTP Verification)
```json
{
  "channel": "email",
  "recipient": "student@tkmce.ac.in",
  "subject": "CixioHub - Email Verification Code",
  "body": "Your verification code is: 582491\n\nThis code is valid for 10 minutes. Please do not share it with anyone.",
  "html_body": "<p>Your verification code is: 582491<br><br>This code is valid for 10 minutes. Please do not share it with anyone.</p>",
  "title": "CixioHub - Email Verification Code",
  "message_type": "otp",
  "priority": "high",
  "data": {}
}
```

### JSON Payload Example (Password Reset)
```json
{
  "channel": "email",
  "recipient": "student@tkmce.ac.in",
  "subject": "CixioHub - Password Reset Request",
  "body": "We received a request to reset the password for your account.\nPlease use the following link to reset your password:\n\nhttp://localhost:3000/auth/reset-password?token=eyJhbGciOi...",
  "html_body": "<p>We received a request to reset the password for your account.<br>Please use the following link to reset your password:<br><br>http://localhost:3000/auth/reset-password?token=eyJhbGciOi...</p>",
  "title": "CixioHub - Password Reset Request",
  "message_type": "password_reset",
  "priority": "high",
  "data": {}
}
```

---

## Reliability & Error Handling

1. **Publisher Retry Mechanism**:
   - The publisher will try to establish a connection and publish the message.
   - If the operation fails, it retries up to **3 times** (total of 4 attempts) with exponential backoff (`2 ** attempt * 0.1` seconds).
   - If all retries fail, it logs the error and raises an exception to trigger local error fallback (which falls back to local log printing to avoid breaking the registration/auth flows).

2. **Persistent Messages**:
   - Messages are published with `delivery_mode=PERSISTENT` (`delivery_mode: 2`) ensuring that they are saved to disk on the RabbitMQ broker to prevent loss in case of a crash or restart.

3. **Durable Queues & Exchanges**:
   - Both the main exchanges (`notification.exchange`, `dla.exchange`) and the queues (`high`, `medium`, `low`, `dla`) are configured as **durable** (`durable=True`).
