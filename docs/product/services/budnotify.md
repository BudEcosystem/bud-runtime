# budnotify - Low-Level Design
---

## 1. Document Overview

### 1.1 Purpose

This LLD provides build-ready technical specifications for budnotify, the notification service of Bud AI Foundry. It wraps Novu to deliver multi-channel notifications across email, SMS, push, and in-app channels.

### 1.2 Scope

**In Scope:**
- Multi-channel notification delivery via Novu
- Subscriber management
- Topic-based broadcast notifications
- Notification templates and workflows
- Integration with external providers (SMTP, Twilio, Firebase)

**Out of Scope:**
- Email/SMS provider implementation (delegated to Novu)
- User authentication (handled by budapp)
- Notification content generation (callers provide content)

---

## 2. System Context & Assumptions

### 2.1 Business Assumptions

- All platform services need to send notifications
- Users have notification preferences
- Multiple channels per notification type
- Notifications must be tracked and auditable

### 2.2 Technical Assumptions

- Novu handles channel delivery
- MongoDB stores notification state
- Dapr pub/sub for async notification triggers
- Idempotent notification delivery

### 2.3 External Dependencies

| Dependency | Type | Failure Impact | Fallback Strategy |
|------------|------|----------------|-------------------|
| Novu | Required | No notifications | Queue and retry |
| MongoDB | Required | No persistence | Return 503 |
| SMTP Provider | Optional | No email | Use alternative channel |
| Twilio | Optional | No SMS | Use alternative channel |
| Firebase | Optional | No push | Use alternative channel |

---

## 3. Detailed Architecture

### 3.1 Component Overview

![Budnotify component overview](./images/budnotify-overview.png)

### 3.2 Notification Types

| Type | Description | Target |
|------|-------------|--------|
| EVENT | Direct to subscriber(s) | subscriber_ids |
| TOPIC | Broadcast to topic subscribers | topic_keys |
| BROADCAST | All subscribers | All registered |

---

---

## 5. API & Interface Design

### 5.1 POST /notifications

**Purpose:** Trigger a notification

### 5.2 Subscriber Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /subscribers | Create subscriber |
| GET | /subscribers/{id} | Get subscriber |
| PUT | /subscribers/{id} | Update subscriber |
| DELETE | /subscribers/{id} | Delete subscriber |
| POST | /subscribers/bulk | Bulk create |

### 5.3 Topic Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /topics | Create topic |
| GET | /topics | List topics |
| POST | /topics/{key}/subscribers | Add subscriber to topic |
| DELETE | /topics/{key}/subscribers/{id} | Remove from topic |

---

## 6. Configuration & Environment

### 6.1 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| MONGODB_URL | Yes | - | MongoDB connection |
| NOVU_API_KEY | Yes | - | Novu API key |
| NOVU_BASE_URL | No | https://api.novu.co | Novu API endpoint |
| SMTP_HOST | No | - | Email server |
| SMTP_PORT | No | 587 | Email port |
| TWILIO_SID | No | - | Twilio account |
| TWILIO_AUTH_TOKEN | No | - | Twilio auth |
| FIREBASE_CREDENTIALS | No | - | Push notifications |

---

## 7. Security Design

### 7.1 API Security

- All endpoints require authentication
- Subscriber IDs validated against user permissions
- Sensitive content not logged

### 7.2 Provider Credentials

- Stored in secrets manager
- Rotated periodically
- Never exposed in responses

---

## 8. Performance & Scalability

### 8.1 Throughput

- Async notification processing
- Batch support for bulk notifications
- Novu handles delivery queuing

### 8.2 Scaling

- Horizontal: Multiple budnotify instances
- Novu: Managed scaling

---

## 9. Deployment & Infrastructure

### 10.1 Resource Requirements

| Component | CPU | Memory |
|-----------|-----|--------|
| budnotify | 250m-500m | 256Mi-512Mi |
