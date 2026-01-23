# budCustomer - Low-Level Design
---

## 1. Document Overview

### 1.1 Purpose

This LLD provides build-ready technical specifications for budCustomer, the customer-facing portal of Bud AI Foundry. It provides usage dashboards, billing, API key management, and support access.

### 1.2 Scope

**In Scope:**
- Usage dashboards and metrics
- Billing and invoice views
- API key management
- Support ticket integration
- Account settings

**Out of Scope:**
- Payment processing (Stripe backend)
- Internal administration (budadmin)
- Model inference (budgateway)

### 1.3 Intended Audience

| Audience | What They Need |
|----------|----------------|
| Frontend Developers | Component architecture |
| Product | Customer features |
| Support | Portal capabilities |

---

## 2. System Context & Assumptions

### 2.1 Business Assumptions

- Customers access via self-service portal
- Billing integrates with Stripe
- API keys are critical for customer access
- Support tickets link to external system

### 2.2 Technical Assumptions

- Next.js frontend
- budapp API for data
- Stripe for payment UI
- External support system integration

### 2.3 External Dependencies

| Dependency | Type | Failure Impact | Fallback Strategy |
|------------|------|----------------|-------------------|
| budapp | Required | No data | Show error |
| Stripe | Optional | No billing UI | Show invoices |
| Support System | Optional | No tickets | Email fallback |

---

## 3. Detailed Architecture

### 3.1 Application Structure

```
src/
├── pages/
│   ├── index.tsx          # Dashboard
│   ├── usage.tsx          # Usage metrics
│   ├── billing/
│   │   ├── index.tsx      # Billing overview
│   │   └── invoices.tsx   # Invoice history
│   ├── api-keys/
│   │   └── index.tsx      # Key management
│   ├── support/
│   │   └── index.tsx      # Support tickets
│   └── settings/
│       └── index.tsx      # Account settings
│
├── components/
│   ├── UsageChart/        # Usage visualization
│   ├── InvoiceList/       # Invoice display
│   ├── ApiKeyTable/       # Key management
│   └── TicketForm/        # Support form
│
└── hooks/
    ├── useUsage.ts        # Usage data fetching
    ├── useBilling.ts      # Billing data
    └── useApiKeys.ts      # Key management
```

---

## 4. Data Design

### 4.1 Usage Data

```typescript
interface UsageMetrics {
  period: {
    start: string;
    end: string;
  };
  total_requests: number;
  total_tokens: number;
  by_model: {
    [model: string]: {
      requests: number;
      input_tokens: number;
      output_tokens: number;
    };
  };
  by_endpoint: {
    [endpoint: string]: {
      requests: number;
      tokens: number;
    };
  };
}
```

### 4.2 API Key Schema

```typescript
interface ApiKey {
  id: string;
  name: string;
  prefix: string;        // First 8 chars for display
  created_at: string;
  last_used_at: string;
  expires_at: string | null;
  permissions: string[];
  status: 'active' | 'revoked' | 'expired';
}
```

---

## 5. API & Interface Design

### 5.1 Usage Endpoint

```typescript
// GET /api/usage?period=monthly
{
  "data": {
    "period": { "start": "2024-01-01", "end": "2024-01-31" },
    "total_requests": 125000,
    "total_tokens": 45000000,
    "by_model": {
      "llama-3.1-70b": { "requests": 100000, "input_tokens": 30000000, "output_tokens": 10000000 }
    }
  }
}
```

### 5.2 API Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/keys | List API keys |
| POST | /api/keys | Create new key |
| DELETE | /api/keys/{id} | Revoke key |
| PUT | /api/keys/{id} | Update key name |

---

## 6. Logic & Algorithm Details

### 6.1 API Key Creation Flow

```
User → Create Key Form → Generate via API → Display Key Once → Store Prefix
                                                    ↓
                              ⚠️ Key shown only once - user must copy
```

### 6.2 Usage Aggregation

- Daily: 24-hour rolling
- Weekly: 7-day rolling
- Monthly: Calendar month
- Custom: User-defined range

---

## 7. GenAI/ML-Specific Design

### 7.1 Token Usage Display

| Metric | Description |
|--------|-------------|
| Input Tokens | Tokens sent in requests |
| Output Tokens | Tokens received in responses |
| Total Tokens | Input + Output |
| Cost | Calculated from token counts |

---

## 8. Configuration & Environment

### 8.1 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| NEXT_PUBLIC_API_URL | Yes | - | budapp API URL |
| NEXT_PUBLIC_STRIPE_KEY | No | - | Stripe publishable key |

---

## 9. Security Design

### 9.1 API Key Security

- Full key shown only on creation
- Only prefix stored for display
- Keys encrypted at rest
- Immediate revocation capability

### 9.2 Authentication

- Keycloak SSO integration
- Session-based authentication
- MFA support (via Keycloak)

---

## 10. Performance & Scalability

### 10.1 Caching

- Usage data cached for 5 minutes
- Invoice list cached for 1 hour
- API key list always fresh

---

## 11. Error Handling & Logging

| Error | User Impact | Handling |
|-------|-------------|----------|
| Usage fetch failed | No metrics | Show cached |
| Key creation failed | No new key | Retry |
| Billing error | No invoices | Support contact |

---

## 12. Deployment & Infrastructure

### 12.1 Build

```bash
npm run build
npm run start
```

### 12.2 Resources

| Component | CPU | Memory |
|-----------|-----|--------|
| budCustomer | 250m | 256Mi |

---

## 13. Testing Strategy

- Unit tests for data formatting
- Component tests for UI
- E2E tests for key management

---

## 14. Limitations & Future Enhancements

### 14.1 Current Limitations

- Basic usage visualization
- External support system
- Limited billing customization

### 14.2 Planned Improvements

1. Advanced usage analytics
2. In-app support chat
3. Usage alerts and notifications
4. Team management

---

## 15. Appendix

### 15.1 Billing Integration

```typescript
// Stripe Elements integration for payment
import { Elements, PaymentElement } from '@stripe/react-stripe-js';
```
