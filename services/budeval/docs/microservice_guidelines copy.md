# 🕸️ Microservice Guidelines

Microservice guidelines define essential practices and recommendations for building and maintaining microservices within
the organization. It will cover topics such as code structure, naming conventions, error handling, logging, security
best practices, and testing strategies. The need for these guidelines stems from the importance of maintaining
consistency, reliability, and scalability across the different microservices in the organization. By adhering to these
guidelines, developers can ensure that the microservices are easy to maintain, integrate seamlessly with each other, and
adhere to industry standards for quality and security.

## Table of Contents

- [Application Structure](#-application-structure)
    - [Commons Modules](#-commons-modules)
    - [Shared Modules](#-shared-modules)
    - [Core Modules](#-core-modules)
    - [Import Practices](#-import-practices)
    - [Comments & Docstrings](#-comments--docstrings)
    - [Configuration & Dependencies](#-configurations--dependencies)
    - [Best Practices](#-best-practices)
- [API Design Practices](./api_design_practices.md)
- [Dapr a Distributed Runtime](./dapr_a_distributed_runtime.md)
    - [Configs & Secrets](./configs_and_secrets.md)
    - [State Store]()
    - [Pub/Sub]()
    - [Database]()
    - [Actors & Bindings]()
    - [Scheduled Jobs]()
    - [Resiliency]()
    - [Observability](./observability.md)
    - [Security]()
- [Unit Testing](./unit_testing.md)
- [Profiling](./profiling.md)
- [Deployment Setup](./deployment.md)
    - [Pre-Requisites](./deployment.md#-pre-requisites)
    - [Build & Deploy](./deployment.md#-build--deploy)
    - [Local Setup & Troubleshooting](./deployment.md#-local-setup--troubleshooting)
    - [Service Invocation](./deployment.md#-service-invocation)

## ⛓️ Application Structure

```markdown
bud-microframe-<name>/  
├── .dpar/                             # Directory for Dapr-specific configurations.  
│   ├── components/                    # Dapr components directory for service bindings, pub-sub, etc.  
│   │   ├── local-secretstore.yaml     # Configuration for local secret management.  
│   │   ├── configstore.yaml           # Configuration for storing application settings.  
│   │   ├── ....                       # Additional Dapr component configurations.  
│   ├── appconfig-dev.yaml             # Dapr configuration for development environment.  
├── deploy/                            # Directory for deployment-related scripts and configurations.  
│   ├── docker-compose-dev.yaml        # Docker Compose file for setting up development environment.  
│   ├── docker-compose-redis.yaml      # Docker Compose file specifically for Redis setup.  
│   ├── Dockerfile                     # Dockerfile for building the Docker image for the service.  
│   ├── start_dev.sh                   # Script to start the development environment.  
│   ├── ....                           # Additional deployment-related scripts or configurations.  
├── docs/                              # Directory for documentation (Sphinx, Markdown, etc.).  
├── <name>/                            # Main application directory.  
│   ├── commons/                       # Shared utilities and common modules.  
│   │   ├── __init__.py                # Initializes the commons module.  
│   │   ├── config.py                  # Configuration management utilities.  
│   │   ├── constants.py               # Constant values used across the application.  
│   │   ├── schemas.py                 # Standard Pydantic models and data validation schemas.  
│   │   ├── exceptions.py              # Custom exceptions used in the application.  
│   │   ├── async_utils.py             # Asynchronous utility functions.  
│   │   ├── logging.py                 # Logging setup and configuration.  
│   │   ├── ....                       # Additional common utilities or modules.  
│   ├── core/                          # Core functionalities and main services.  
│   │   ├── __init__.py                # Initializes the core module.  
│   │   ├── routes.py                  # API route definitions.
│   │   ├── meta_routes.py             # API route definitions for metadata endpoints.  
│   │   ├── sync_routes.py             # API route definitions for sync endpoints.
│   │   ├── schemas.py                 # Pydantic models and data validation schemas.  
│   │   ├── services.py                # Core service logic and business rules.  
│   │   ├── ....                       # Additional core functionalities.  
│   ├── module_a/                      # Specific module or feature A.  
│   │   ├── __init__.py                # Initializes module A.  
│   │   ├── models.py                  # Data models specific to module A.  
│   │   ├── routes.py                  # API routes related to module A.  
│   │   ├── schemas.py                 # Validation schemas for module A.  
│   │   ├── ....                       # Additional code specific to module A.  
│   ├── module_b/                      # Specific module or feature B.  
│   │   ├── __init__.py                # Initializes module B.  
│   │   ├── models.py                  # Data models specific to module B.  
│   │   ├── routes.py                  # API routes related to module B.  
│   │   ├── schemas.py                 # Validation schemas for module B.  
│   │   ├── ....                       # Additional code specific to module B.  
│   ├── shared/                        # Shared components between modules.  
│   │   ├── __init__.py                # Initializes the shared module.  
│   │   ├── dapr_service.py            # Service wrapper for Dapr interactions.  
│   │   ├── ....                       # Additional shared services or utilities.  
│   ├── __about__.py                   # Metadata about the project (e.g., version, author).  
│   ├── __init__.py                    # Initializes the main application module.  
│   ├── py.typed                       # Marker file indicating the package uses type hints.  
│   └── main.py                        # Entry point for the application.  
├── tests/                             # Directory for unit and integration tests.  
│   ├── conftest.py                    # Test configuration and fixtures.  
│   ├── module_a/                      # Tests related to module A.  
│   ├── module_b/                      # Tests related to module B.  
│   ├── ....                           # Additional test scripts.  
|   └── profiling/                     # Scripts for application memory & time benchmarking and load testing.  
├── scripts/                           # Utility scripts for managing the project.  
│   ├── del_configs.sh                 # Script to delete specific configurations.  
│   ├── update_configs.sh              # Script to update configurations.  
│   ├── ....                           # Additional utility scripts.  
├── sample.secrets.json                # Sample file for managing secrets (should not be used in production).  
├── .dockerignore                      # Specifies files and directories to ignore when creating a Docker image.  
├── .commitlintrc.yaml                 # Configuration for commit message linting.  
├── .pre-commit-config.yaml            # Configuration for pre-commit hooks.  
├── .gitignore                         # Specifies files and directories to ignore in Git.  
├── setup.py                           # Script for installing the package.  
├── pyproject.toml                     # Project metadata and configuration file.  
├── requirements.txt                   # Production dependencies for the project.  
├── requirements-dev.txt               # Development dependencies for the project.  
├── requirements-lint.txt              # Linting dependencies for the project.  
├── requirements-test.txt              # Testing dependencies for the project.  
├── LICENSE                            # License file for the project.  
└── README.md                          # Project overview and documentation.
```

### 📁 Commons Modules

The `commons` module is a crucial part of your microservice architecture, designed to focus on low-level utilities,
configurations, and reusable code that has a broad application within the project. Here's a breakdown of what files
should be placed in this module and their purposes:

**Utility Functions** (`async_utils.py`, `helpers.py`, etc.):

- **Purpose**: Store commonly used helper functions that perform specific tasks like date manipulations, string
  operations, or asynchronous utilities.
- **Example**: `async_utils.py` might contain functions to simplify the handling of asynchronous tasks,
  while `helpers.py` could include functions like `format_date`, `capitalize_string`, etc.

**Custom Exceptions** (`exceptions.py`):

- **Purpose**: Define custom exception classes that are used across the application to handle errors in a consistent
  manner.
- **Example**: `exceptions.py` could contain custom exceptions like `ValidationError`, `AuthenticationError`,
  or `DatabaseError`,which can be raised and caught throughout the application.

**Configuration Files** (`config.py`):

- **Purpose**: Manage and centralize configuration settings that are shared across different parts of the application,
  such as environment variables, database connections, and API keys.
- **Example**: `config.py` handle the loading of environment-specific settings and default configuration values.

**Logging Setup** (`logging.py`):

- **Purpose**: Centralize the logging configuration, ensuring that all parts of the application follow a consistent
  logging format and level.
- **Example**: `logging.py` include the setup for loggers, handlers, and formatters, along with utility functions to log
  messages in a standardized way across the service.

**Common Middlewares** (`profiler_middleware.py`, `cors_middleware.py`):

- **Purpose**: Define middleware that applies to multiple routes or modules within the application, ensuring consistent
  handling of concerns like authentication, cross-origin resource sharing (CORS), or request logging.
- **Example**: `profiler_middleware.py` might include logic to calculate time profiles of requests,
  while `cors_middleware.py` handles CORS policies across the application.

**Validation Logic** (`validators.py`):

- **Purpose**: Centralize validation logic, such as input validation or schema enforcement, that is used across
  different parts of the application.
- **Example**: `validators.py` might contain functions or classes to validate request payloads, ensuring data integrity
  before processing.

**Response Handling** (`responses.py`):

- **Purpose**: Define common response formats or utility functions for generating API responses in a standardized way.
- **Example**: `responses.py` provide functions like `success_response`, `error_response`, or `paginate_response`, which
  are used across various endpoints to ensure consistent API output.

#### Additional Considerations

- **Consistency**: The commons module should aim to reduce code duplication and promote the DRY (Don't Repeat Yourself)
  principle by centralizing logic that is used in multiple places.
- **Modularity**: Each file within the commons module should be self-contained and focused on a specific aspect of the
  application, making it easy to understand, maintain, and reuse.
- **Documentation**: Ensure that each module within the commons module is well-documented, with clear descriptions of
  what each function or class does, and when it should be used.

### 📁 Shared Modules

The `shared` module typically contains modules and components that are used across different parts of your application
but are not just utilities. This module is typically for components that, while shared, are more tied to the business
logic or architecture of the application than the more generic utilities found in the `commons` module. The `shared`
module provides a place for code that needs to be reused across the application but is still part of the core
functionality. These might include:

**Shared Models**: Database models that are used across different modules of the application.

- **Example**: `models.py` (This could include shared ORM models that different parts of the application rely on.)

**Service Classes**: Classes that provide shared services or business logic used across various parts of the
application.

- **Example**: `email_service.py`, `payment_service.py`, `dapr_service.py` (Services that encapsulate core business
  functionalities.)

### 📁 Core Modules

The `core` module is a critical component of the project, designed to contain the essential functionalities and
services that form the backbone of the application. This module serves as the central hub for business logic, core
services, and fundamental operations that are pivotal to the application’s operation. Below is an overview of building
blocks in the `core` module that support the application's operations.

**Routes**:

- `routes.py`: For projects with simple business logic, all routes can be consolidated into this single file.
- **Naming Convention**: If the project has multiple business logics, routes should be split into separate files based
  on the logic they handle. For example:
    - `meta_routes.py`: Handles metadata-related routes.
    - `sync_routes.py`: Handles synchronization-related routes.
- **Modular Structure**: If the routes are complex or involve independent services, schemas, models, etc., it is
  advisable to split them into separate modules (e.g., `module_a`, `module_b`) at the same level as core. Each of these
  modules should follow a similar structure as the core.

**Schemas** (`schemas.py`): Contains Pydantic models and other schema definitions that outline the structure of the data
used in the module routes
and services.

**Models** (`models.py`): This file is required only when the project involves database interactions. It contains the
ORM models that map to the
database tables.

**Services** (`services.py`): This is where the business logic resides. It includes functions and classes that
encapsulate the module's operations and
workflows.

**Utilities** (`utils.py`): This file is optional and should be included only if there are multiple utility functions or
classes that are specific
to the core module. These utilities shouldn't be used anywhere outside it's module scope.

**Dependencies** (`dependencies.py`): Contains functions or classes that define dependencies specific to a module. These
are typically injected into
routes or services where needed.

**Middlewares** (`middlewares.py`): If a module requires specific middleware, they can be defined here. This is optional
and should be used only when
the middleware is not generic enough to be placed in commons.

**Exceptions** (`exceptions.py`): Defines custom exceptions that are specific to a module. This file is optional and
should be used only if there
are multiple exceptions or if they are utilized across various scripts within the module.

**Validators** (`validators.py`): Contains validation functions or classes specific to a module. This file is optional
and should be included only
if there are complex validation requirements.

### 🧩️ Import Practices

#### Absolute Imports for Inter-Module Dependencies

To maintain clarity and consistency across the project, absolute imports should be used when importing modules or
components from different modules within the project. Absolute imports help in clearly identifying the location of the
module and reduce the risk of import errors during refactoring.

**Example**:

```python
# Importing a service from the core module into module_a
from core.services import AuthService

# Importing a utility from the commons module into core
from commons.logging import setup_logging
```

#### Relative Imports for Intra-Module Dependencies

When dealing with components within the same module, relative imports are preferred. This approach keeps the module
self-contained and reduces the dependency on the overall project structure.

**Example**:

```python
# Importing a helper function within the same module
from .utils import calculate_discount

# Importing a schema within the same module
from .schemas import UserSchema
```

#### Why Use Absolute Imports for Inter-Module Imports?

- **Clarity**: Absolute imports make it clear where a module is located within the project structure. This can help in
  understanding the overall architecture of the project.
- **Maintainability**: As the project grows, absolute imports reduce the likelihood of import errors caused by
  refactoring or moving files around.
- **Consistency Across the Project**: Absolute imports provide a consistent way to access modules, which is particularly
  useful when working with large teams or when the codebase scales.

#### Why Use Relative Imports for Intra-Module Imports?

- **Simplicity**: Relative imports simplify the import statements within a module, especially when the module's
  components are closely related and should be treated as a cohesive unit.
- **Encapsulation**: It encourages keeping the module's internal components tightly coupled within the module itself,
  reducing dependencies across the entire project.
- **Easier Refactoring**: If you move a module or its components, relative imports within the module usually don't need
  to be adjusted, simplifying refactoring.

### 📝 Comments & Docstrings

#### 〰️ Docstring Guidelines

- Use the Google Docstring format for all functions, classes, and modules.
- Start with a short description of the function or class.
- Include descriptions for all parameters and return values.
- Provide examples if necessary.
- Indicate any exceptions raised by the function.

#### 💬 Comment Guidelines

- Use inline comments sparingly and only when the code is not immediately clear.
- Block comments should explain sections of code that perform complex tasks.
- Keep comments up to date with the code. Remove outdated or incorrect comments to avoid confusion.

### ⚙️ Configurations & Dependencies

- 📄 `__about__.py`: A python script in the project root directory (or inside the package if there is one). This file
  typically contains metadata about the project, such as version information.
  For example, if your project is named `myproject` and the version is 0.1.0, your `__about__.py` file should look like
  this:

   ```python
    # myproject/__about__.py

    __version__ = "myproject@0.1.0"
   ```
  If the package is located in a different folder, adjust the path accordingly.
- 📄 `requirements-lint.txt`: Contains the list of linting dependencies required for maintaining code quality. This
  file is used to ensure that your code adheres to style and quality standards.
- 📄 `requirements-dev.txt`: Includes the development dependencies needed for building, testing, and developing the
  project. This often includes testing frameworks, linters, and other tools.
- 📄 `pyproject.toml`: A configuration file used for project metadata and tool settings. This file defines the build
  system, dependencies, and other configurations for tools like black, mypy, and ruff.
- 📄 `setup.py`: The setup script for the project, used to define the package metadata and dependencies. This file is
  essential for packaging and distributing your project. Below are some of the fields that might require changes to
  reflect relevant project metadata:
    - **description**: Provide a brief description of your project.
    - **packages**: List the packages to be included in the distribution.
    - **package_data**: Specify any additional files to be included in the package.
    - **other relevant fields**: Update any other fields as necessary, such as email, license, etc.
- 📄 `.pre-commit-config.yaml`: Configuration file for pre-commit hooks. This file specifies the hooks to be run
  before each commit to ensure code quality and formatting.
- 📄 `.commitlintrc.yaml`: Configuration file for commitlint. This file specifies the conventional commit
  configurations to be applied while linting the commit message.

### 😎 Best Practices

- **Keep `commons` and `shared` Lightweight**: Ensure that these folders only contain truly generic and reusable
  components that can be safely imported by any part of the application.
- **Avoid Importing Back into `commons` and `shared`**: If you find yourself needing to import core or other
  application-specific modules back into commons or shared, it's a sign that these utilities might be too tightly
  coupled with application logic.
- **Single Module Simplicity**: If your project is relatively simple with a limited amount of business logic, consider
  keeping everything within the core module. A single routes.py file along with schemas.py, models.py, and services.py
  can be sufficient for such projects.
- **Modular Complexity**: For more complex projects, split the routes and related components (schemas, services, etc.)
  into separate files or even into their own modules at the same level as core. For instance, you could have separate
  modules like module_a, module_b, etc., each containing its own routes, schemas, models, and other components.
- **Naming Conventions**: Use clear and consistent naming conventions for your routes files. For example, if you have
  multiple routers in core, create separate files such as meta_routes.py and sync_routes.py to ensure that each set of
  related routes is easy to locate and manage.
- **Avoiding Over-Engineering**: While modularity is crucial, avoid over-engineering. Split components only when
  necessary to maintain readability, simplicity, and ease of maintenance.
- **Clear Separation of Concerns**: Ensure that each module or component is designed to handle specific tasks without
  unnecessary dependencies. This approach not only improves clarity but also minimizes the risk of circular imports and
  other structural issues.
- Use **absolute imports** for inter-module dependencies to ensure clarity and ease of maintenance.
- Use **relative imports** for intra-module dependencies to keep modules self-contained and to simplify internal
  refactoring.
- **Clarity**: Ensure comments and docstrings are clear, concise, and meaningful.
- **Relevance**: Add comments where the code might not be self-explanatory, explaining the intent and logic behind the
  code.
- **Link References**: If code or logic is adapted from external sources or relevant documentation, include the
  corresponding links in the comments or docstrings.
- **Consistency**: Maintain consistent comment and docstring style throughout the codebase.