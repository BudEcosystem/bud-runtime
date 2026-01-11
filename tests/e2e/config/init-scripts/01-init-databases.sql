-- Create databases for E2E testing
CREATE DATABASE keycloak_e2e;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE keycloak_e2e TO testuser;
GRANT ALL PRIVILEGES ON DATABASE budapp_e2e TO testuser;

-- Connect to budapp_e2e and enable extensions
\c budapp_e2e
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
