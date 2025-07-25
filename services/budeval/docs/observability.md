# 👀 Observability: Keeping an Eye on Your Microservices

Observability is all about understanding what's happening inside your microservices at any given moment. By collecting
and analyzing logs, traces, and metrics, you gain valuable insights into the health, performance, and behavior of your
application. This section will guide you through the best practices for logging, tracing, and more to ensure your
microservices are as transparent and predictable as possible.

## Table of Contents

- [Logging](#-logging-best-practices-for-observability)

## 🛠️ Logging: Best Practices for Observability

**Logging** is the first step in making your microservices observable. Properly configured logs allow you to track the
flow of execution, diagnose issues, and monitor the performance of your application in real-time. Let’s dive into the
best practices for logging to ensure your services are as observable as they are resilient.

### 🚀 Getting Started with Logging

Your microservice already has a preconfigured logger ready to go. This logger is designed to be your go-to for all
logging needs, ensuring that your logs are consistent, structured, and easy to manage.

To get started with logging in any file, simply import and set up your logger like this:

```python
from pyguard.commons import logging

logger = logging.get_logger(__name__)
```

This ensures that every log message is tagged with the module name, making it easier to track down where the logs are
coming from.

#### ❗ No More print Statements!

Ditch those print statements. Seriously. Instead, use:

- `logger.debug("Debugging information here")`: For detailed information, typically of interest only when diagnosing
  problems.
- `logger.info("Just an info update")`: For informational messages that highlight the progress of the application.
- `logger.warning("Something might be wrong")`: For an indication that something unexpected happened, or indicative of
  some problem in the near future.
- `logger.error("Something went wrong")`: For errors that are more severe but the application is still running.
- `logger.exception("An exception occurred")`: For logging errors along with their stack traces, particularly useful in
  except blocks.
- `logger.critical("We have a critical issue")`: For very severe error events that might cause the application to abort.

These logging levels help categorize the importance of log messages, making it easier to filter and review them when
needed.

#### ❗ Log Exceptions Like a Pro!

Use `logger.exception("An exception occurred")` when you need to log an error **along with its stack trace**. This is
particularly useful in except blocks, where you want to capture the entire context of an error, not just the fact that
it occurred.

- **When to use `logger.error`**: Use this when you want to log an error message without a stack trace, perhaps for
  anticipated issues where the stack trace isn't needed.
- **When to use `logger.exception`**: Use this when you're dealing with unexpected errors in an except block and you
  want to capture the full stack trace to help diagnose the problem.

This distinction helps in maintaining clarity in your logs, making it easier to troubleshoot issues down the line.

### ⚡ Async Logging: When Speed Matters

The logger you’re using supports asynchronous logging, which is particularly useful in high-traffic parts of your code.
Async logging ensures that your application remains responsive even when logging large volumes of data.

**Example**:

```python
from pyguard.commons import logging

logger = logging.get_logger(__name__)


async def function():
    ...
    await logger.ainfo("Async info message")
    ...

```

For more information, refer to
the [Structlog Asyncio documentation](https://www.structlog.org/en/stable/getting-started.html#asyncio).

Here are some best practices for async logging:

- **Use Async Logging in High-Traffic Areas**: If a section of your code is hit frequently, or you anticipate a lot of
  log entries, async logging helps maintain performance.
- **Consistency is Key**: Even when using async logging, ensure that log messages are consistent in format and content.
- **Monitor for Log Overhead**: While async logging is efficient, be mindful of any potential overhead or performance
  impacts, especially under heavy load.

### 🎛️ Configuring Log Levels

Log levels can be easily configured using the LOG_LEVEL environment variable. For example:

```shell
export LOG_LEVEL=INFO
```

By default, if your application is running in a development environment, the log level is set to DEBUG to give you all
the details you need while coding.

### 💡 Why Logging Matters

Logging is more than just a tool for debugging—it's a critical part of your observability strategy. Proper logging gives
you insights into the health and behavior of your microservices, making it easier to diagnose issues, track performance,
and understand user behavior.