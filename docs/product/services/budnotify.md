# budnotify Service Documentation

---

## Overview

budnotify is the notification service that wraps Novu to provide multi-channel notifications including email, SMS, push, and in-app messages.

---

## Service Identity

| Property | Value |
|----------|-------|
| **App ID** | budnotify |
| **Port** | 9088 |
| **Database** | budnotify_db (MongoDB) |
| **Language** | Python 3.11 |
| **Framework** | FastAPI |

---

## Responsibilities

- Send notifications via multiple channels
- Manage notification templates
- Track notification delivery status
- User notification preferences
- Integrate with Novu backend

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/notifications/send` | Send notification |
| GET | `/notifications` | List notifications |
| GET | `/notifications/{id}` | Get notification status |
| GET | `/templates` | List templates |
| POST | `/templates` | Create template |
| GET | `/preferences/{user_id}` | Get user preferences |
| PUT | `/preferences/{user_id}` | Update preferences |

---

## Notification Channels

| Channel | Provider | Description |
|---------|----------|-------------|
| `email` | SMTP/SendGrid | Email notifications |
| `sms` | Twilio | SMS messages |
| `push` | Firebase | Push notifications |
| `in_app` | Novu | In-application notifications |
| `slack` | Slack API | Slack messages |

---

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URL` | MongoDB connection string | Required |
| `NOVU_API_KEY` | Novu API key | Required |
| `SMTP_HOST` | Email server | Optional |
| `TWILIO_SID` | Twilio account SID | Optional |

---

## Related Documents

- [Notification Configuration](../operations/notification-config.md)
