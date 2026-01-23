# budCustomer Service Documentation

---

## Overview

budCustomer is the customer-facing portal providing usage dashboards, billing views, API key management, and support access for end customers.

---

## Service Identity

| Property | Value |
|----------|-------|
| **App ID** | budCustomer |
| **Port** | 8009 |
| **Language** | TypeScript 5.x |
| **Framework** | Next.js |
| **UI Library** | React |

---

## Responsibilities

- Customer usage dashboards
- Billing and invoice views
- API key management
- Support ticket access
- Documentation portal
- Account settings

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Usage Dashboard** | View API usage and metrics |
| **Billing** | Invoices, payment history |
| **API Keys** | Create, rotate, revoke keys |
| **Support** | Submit and track tickets |
| **Docs** | Embedded documentation |

---

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | budapp API URL | Required |
| `NEXT_PUBLIC_STRIPE_KEY` | Stripe publishable key | Optional |

---

## Development

```bash
cd services/budCustomer
npm install
npm run dev
```

---

## Related Documents

- [Customer Portal Guide](../training/customer-portal.md)
- [API Key Management](../api/api-authentication.md)
