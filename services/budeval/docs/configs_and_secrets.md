# 🔐 Configs and Secrets: Safeguarding Your Microservice

When it comes to microservices, managing configurations and secrets securely and efficiently is crucial. Let's dive into
how we've structured this and the best practices to follow.

## Table of Contents

- [AppConfig](#-appconfig-the-configuration-blueprint)
- [SecretsConfig]()

## 📄 AppConfig: The Heart of Configuration Management

At the heart of our configuration management is the `AppConfig` class, defined in `commons/config.py`. This
structure is crucial for mapping configurations related to your microservice, ensuring that the service is both flexible
and robust.

### 🚦 Mandatory Fields

The existing fields in `AppConfig` are all mandatory. This design choice ensures that essential configurations are
always present, minimizing the risk of unexpected behavior due to missing settings.

### ➕ Adding New Fields

When adding new fields, adhere to Pydantic guidelines. Each field should be declared with a type and, if configurable
via environment variables, use the format:

```python
fieldname: < type > = Field(default, alias="ENV VARIABLE NAME")
```

This approach allows for easy overriding of configuration values via environment variables, which is particularly useful
in dynamic environments where these values may change.

### 🌍 Environment Variables

Use environment variables primarily when configuration values cannot be stored in the config store, such as
environment-specific settings. The advantage of using environment variables is the ability to change these values
without modifying the code or restarting the service, providing flexibility in deployment and operations.

### 🛠️ Redis as the Config Store

Configurations are stored in Redis, which is configured as a Dapr component in `.dapr/components/configstore.yaml`.

- **When to Modify**: Typically, you won’t need to alter this configuration. However, if modifications are necessary,
  follow the guidelines in the Deployment section to ensure that changes are applied correctly, particularly if they are
  local environment-specific.
- **What to Add**: Your config store can include anything from application-specific settings to feature flags.
  Centralized management of configurations simplifies updates and reduces the need for direct codebase changes. When you
  add an application specific config you will need to use the naming convention `<app name>.<key name>`. For example if
  you want to add a config `debug` for app `pyguard` you need to set the key name as `pyguard.debug`.

### 🔄 Syncing Configs: The Best of Both Worlds

The `AppConfig` Fields supports a `json_extra_schema`, where fields can be defined to sync from the config store. For
example:

```python
debug: Optional[bool] = Field(
    None,
    alias="DEBUG",
    json_schema_extra=SyncDetails(sync=True, key_prefix=f"{name}.").__dict__,
)
```

- **Syncing from Config Store**: By setting `sync=True`, the field will be synced from the config store. The field name
  is used as the key by default, but you can use `key_prefix` or `alias` to match different naming conventions in the
  config store.
- **Sync Interval**: The microservice syncs fields with sync enabled at startup and at intervals defined by `
  BaseConfig`'s `max_sync_interval` (default 12 hours). This interval optimizes performance by leveraging caching,
  preventing frequent hits to the config store. To change the sync interval, set the `MAX_STORE_SYNC_INTERVAL` in
  seconds.
  **Note**: Avoid changing this in the code unless necessary (e.g., during debugging), and always revert changes before
  committing.

### 📝 Usage Example

To access configurations, simply import `app_settings` from `pyguard.commons.config` and integrate it into your logic:

```python
from pyguard.commons.config import app_settings

# Your logic here
if app_settings.env == "dev":
    # Development-specific logic
    ...
```

This setup ensures that your microservice remains flexible, secure, and scalable, with hassle-free configuration
management.

### 🔧 Script-Based Configuration Management

For managing key-value pairs in the Redis-backed config store, two scripts are provided: `update_configs.sh` and
`del_configs.sh`.

#### 📝 `scripts/update_configs.sh`

This script is used to add key-value pairs to the configuration store. It requires a container name and supports an
optional Redis password. Key-value pairs can be added using --key value syntax.

**Example Usage**:

```shell
./scripts/update_configs.sh --container my_container --password my_password --key1 value1 --key2 value2
```

This command will add the specified key-value pairs to the config store within the specified container.

#### 🗑️ `scripts/del_configs.sh`

This script is used to remove keys from the configuration store. Like the update script, it requires a container name
and supports an optional Redis password. Keys to be deleted can be specified using `--key`.

**Example Usage**:

```shell
./scripts/del_configs.sh --container my_container --password my_password --key1 --key2
```

This command will delete the specified keys from the config store in the specified container.

### ⚙️ Best Practices

- **Centralized Configuration**: Use the config store to centralize and manage all configurations. This reduces the
  complexity of managing environment variables and ensures consistency across deployments.
- **Minimal Environment Variables**: Limit the use of environment variables to scenarios where they are absolutely
  necessary. Prefer the config store for most configurations.
- **Sync Efficiently**: Leverage the sync functionality to keep configurations up to date without frequent hits to the
  config store. This balances performance with the need for updated configurations.
- **Naming Convention**: All config names should follow the `snake_case` format to maintain consistency and
  readability.

**Need More Details?** Dive deeper into Dapr Configuration Management by checking out the
official [Dapr documentation](https://docs.dapr.io/developing-applications/building-blocks/configuration/howto-manage-configuration/)

## 🔐 Secrets Management: Keeping Your Application Secure

In our microservice framework, managing secrets securely is crucial. The `SecretsConfig` class in `commons/config.py` is
designed for this purpose. Here's how to effectively manage your secrets:

### 🗝️ The Essentials

- **Mandatory Fields**: The `dapr_api_token` is the only mandatory field in `SecretsConfig`. Other fields provided are
  placeholders or dummy fields that can be removed as per your requirements.
- **Adding New Secrets**: Adding a new secret is similar to adding a configuration field, but with one key difference:
  environment variables are not allowed for secrets. All secrets must be configured via the secret store.

### 🔧 Local Development with Dapr Secret Store

For development, we use Dapr's local secret store, configured by `.dapr/components/local-secretstore.yaml`. This setup
expects a `secrets.json` file at the root of your project.

- **secrets.json**: This file contains all your secrets. **Important**: Never push this file to your repository. It
  should be kept secure and out of version control.
- **sample.secrets.json**: Maintain a `sample.secrets.json` with the exact structure as `secrets.json`, but without the
  actual values. This serves as a reference for developers, indicating what secrets need to be configured for the
  project.
- **Naming Conventions**: All secret names should follow the `snake_case` format to maintain consistency and
  readability.

### 🔄 Syncing Secrets: The Seamless Integration

Similar to `AppConfig`, the `SecretsConfig` class supports the same syncing mechanism for fields. You can enable sync
for fields using the `json_extra_schema` as shown earlier.

- **Sync Mechanism**: Secrets are synced at startup and then at intervals defined by `BaseConfig` `max_sync_interval`.
  This ensures efficient and secure access to secrets without constant queries to the secret store.

**Need More Details?** Dive deeper into Dapr Secrets Management by checking out the
official [Dapr documentation](https://docs.dapr.io/developing-applications/building-blocks/secrets/secrets-overview/)

### 📝 Usage Example

To access secrets, simply import `secrets_settings` from `pyguard.commons.config` and integrate it into your logic:

```python
from pyguard.commons.config import secrets_settings

# Your logic here
if secrets_settings.budserve_url == "dev":
    # Development-specific logic
    ...
```

### 🚀 Production Environment

For production, a different secret store will be used. This is where the `sample.secrets.json` file becomes crucial, as
it provides the exact structure needed for setting up secrets in the production environment.

By following these practices, you can ensure that your application's secrets are managed securely and efficiently,
reducing the risk of exposure and maintaining compliance with best practices.

