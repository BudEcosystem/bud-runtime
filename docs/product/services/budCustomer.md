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

---

---

## 5. API & Interface Design

### 5.2 API Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/keys | List API keys |
| POST | /api/keys | Create new key |
| DELETE | /api/keys/{id} | Revoke key |
| PUT | /api/keys/{id} | Update key name |

---

## 6. Configuration & Environment

### 6.1 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| NEXT_PUBLIC_API_URL | Yes | - | budapp API URL |
| NEXT_PUBLIC_STRIPE_KEY | No | - | Stripe publishable key |

---

## 7. Security Design

### 7.1 API Key Security

- Full key shown only on creation
- Only prefix stored for display
- Keys encrypted at rest
- Immediate revocation capability

### 7.2 Authentication

- Keycloak SSO integration
- Session-based authentication
- MFA support (via Keycloak)

---

## 8. Performance & Scalability

### 8.1 Caching

- Usage data cached for 5 minutes
- Invoice list cached for 1 hour
- API key list always fresh

---

## 9. Deployment & Infrastructure

### 10.2 Resources

| Component | CPU | Memory |
|-----------|-----|--------|
| budCustomer | 250m | 256Mi |
