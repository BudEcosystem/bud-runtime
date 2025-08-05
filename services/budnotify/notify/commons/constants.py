#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""Defines constant values used throughout the project, including application-specific constants."""

from enum import Enum


class LogLevel(Enum):
    """Define logging levels with associated priority values.

    Inherit from `str` and `Enum` to create a logging level enumeration. Each level has a string representation and a
    corresponding priority value, which aligns with Python's built-in `logging` module levels.

    Attributes:
        DEBUG (LogLevel): Represents debug-level logging with a priority value of `logging.DEBUG`.
        INFO (LogLevel): Represents info-level logging with a priority value of `logging.INFO`.
        WARNING (LogLevel): Represents warning-level logging with a priority value of `logging.WARNING`.
        ERROR (LogLevel): Represents error-level logging with a priority value of `logging.ERROR`.
        CRITICAL (LogLevel): Represents critical-level logging with a priority value of `logging.CRITICAL`.
        NOTSET (LogLevel): Represents no logging level with a priority value of `logging.NOTSET`.
    """

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    NOTSET = "NOTSET"


class Environment(str, Enum):
    """Enumerate application environments and provide utilities for environment-specific settings.

    Inherit from `str` and `Enum` to define application environments with associated string values. The class also
    includes utility methods to convert string representations to `Environment` values and determine logging and
    debugging settings based on the environment.

    Attributes:
        PRODUCTION (Environment): Represents the production environment.
        DEVELOPMENT (Environment): Represents the development environment.
        TESTING (Environment): Represents the testing environment.
    """

    PRODUCTION = "PRODUCTION"
    DEVELOPMENT = "DEVELOPMENT"
    TESTING = "TESTING"

    @staticmethod
    def from_string(value: str) -> "Environment":
        """Convert a string representation to an `Environment` instance.

        Use regular expressions to match and identify the environment from a string. Raise a `ValueError` if the string
        does not correspond to a valid environment.

        Args:
            value (str): The string representation of the environment.

        Returns:
            Environment: The corresponding `Environment` instance.

        Raises:
            ValueError: If the string does not match any valid environment.
        """
        import re

        matches = re.findall(r"(?i)\b(dev|prod|test)(elop|elopment|uction|ing|er)?\b", value)

        env = matches[0][0].lower() if len(matches) else ""
        if env == "dev":
            return Environment.DEVELOPMENT
        elif env == "prod":
            return Environment.PRODUCTION
        elif env == "test":
            return Environment.TESTING
        else:
            raise ValueError(
                f"Invalid environment: {value}. Only the following environments are allowed: "
                f"{', '.join(map(str, Environment.__members__))}"
            )

    @property
    def log_level(self) -> LogLevel:
        """Return the appropriate logging level for the current environment.

        Returns:
            LogLevel: The logging level for the current environment.
        """
        return {"PRODUCTION": LogLevel.INFO}.get(self.value, LogLevel.DEBUG)

    @property
    def debug(self) -> bool:
        """Return whether debugging is enabled for the current environment.

        Returns:
            bool: `True` if debugging is enabled, `False` otherwise.
        """
        return {"PRODUCTION": False}.get(self.value, True)


class NovuEmailProviderId(Enum):
    """Enumeration of email provider IDs for Novu integration.

    This enum defines all possible email providers supported by Novu. Each
    provider corresponds to a specific email service used for sending emails.

    Attributes:
        MAILTRAP: Mailtrap email provider.
        BRAZE: Braze email provider.
        PLUNK: Plunk email provider.
        SENDGRID: SendGrid email provider.
        MAILJET: Mailjet email provider.
        POSTMARK: Postmark email provider.
        MAILGUN: Mailgun email provider.
        SENDINBLUE: Sendinblue email provider.
        MANDRILL: Mandrill email provider.
        SES: Amazon SES email provider.
        MAILERSEND: MailerSend email provider.
        MICROSOFT_OUTLOOK365: Microsoft Outlook 365 email provider.
        RESEND: Resend email provider.
        INFOBIP: Infobip email provider.
        EMAIL_WEBHOOK: Email Webhook provider.
        NETCORE: Netcore email provider.
        CUSTOM_SMTP: Custom SMTP email provider (e.g., Nodemailer).
        SPARKPOST: SparkPost email provider.
    """

    MAILTRAP = "mailtrap"
    BRAZE = "braze"
    PLUNK = "plunk"
    SENDGRID = "sendgrid"
    MAILJET = "mailjet"
    POSTMARK = "postmark"
    MAILGUN = "mailgun"
    SENDINBLUE = "sendinblue"
    MANDRILL = "mandrill"
    SES = "ses"
    MAILERSEND = "mailersend"
    MICROSOFT_OUTLOOK365 = "outlook365"
    RESEND = "resend"
    INFOBIP = "infobip-email"
    EMAIL_WEBHOOK = "email-webhook"
    NETCORE = "netcore"
    CUSTOM_SMTP = "nodemailer"
    SPARKPOST = "sparkpost"


class NovuChannel(Enum):
    """Represents various communication channels supported by Bud's notification system.

    Attributes:
        SMS: Represents the SMS communication channel.
        EMAIL: Represents the email communication channel.
        CHAT: Represents the chat communication channel.
        PUSH: Represents the push notification communication channel.
    """

    SMS = "sms"
    EMAIL = "email"
    CHAT = "chat"
    PUSH = "push"


# Mapping of Novu channel to provider
NOVU_CHANNEL_PROVIDER_MAPPING = {
    "email": {
        "mailtrap": "Mailtrap",
        "braze": "Braze",
        "plunk": "Plunk",
        "sendgrid": "SendGrid",
        "mailjet": "Mailjet",
        "postmark": "Postmark",
        "mailgun": "Mailgun",
        "sendinblue": "Sendinblue",
        "mandrill": "Mandrill",
        "ses": "SES",
        "mailersend": "MailerSend",
        "outlook365": "Microsoft Outlook365",
        "resend": "Resend",
        "infobip-email": "Infobip",
        "email-webhook": "Email Webhook",
        "netcore": "Netcore",
        "nodemailer": "Custom SMTP",
        "sparkpost": "SparkPost",
    }
}


class NotificationType(Enum):
    """Represents the type of a notification.

    Attributes:
        EVENT: Notification triggered by an event.
        TOPIC: Notification related to a specific topic.
        BROADCAST: Notification triggered by a broadcast.
    """

    EVENT = "event"
    TOPIC = "topic"
    BROADCAST = "broadcast"  # TODO: bulk event triggering


class NotificationCategory(str, Enum):
    """Represents the type of an internal notification.

    Attributes:
        INAPP: Represents the in-app notification type.
        INTERNAL: Represents the internal notification type.
    """

    INAPP = "inapp"
    INTERNAL = "internal"


class WorkflowStatus(str, Enum):
    """Enumerate workflow statuses."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
