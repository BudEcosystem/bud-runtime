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

"""Provides utility functions and wrappers for interacting with Dapr components, including service invocation, pub/sub, and state management."""

import json
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from dapr.clients import DaprClient
from dapr.clients.grpc.client import ConfigurationResponse
from dapr.conf import settings as dapr_settings

from notify.commons import logging
from notify.commons.config import app_settings, secrets_settings
from notify.commons.exceptions import SuppressAndLog


logger = logging.get_logger(__name__)


class DaprService(DaprClient):
    """A service class for interacting with Dapr, providing methods for syncing configurations and secrets.

    Inherits from:
        DaprClient: Base class for Dapr client operations.

    Args:
        api_method_invocation_protocol (Optional[str]): The protocol used for API method invocation.
            Defaults to the value in `app_settings.dapr_api_method_invocation_protocol`.
        health_timeout (Optional[int]): Timeout for health checks. Defaults to the value in
            `app_settings.dapr_health_timeout`.
        **kwargs: Additional keyword arguments passed to the `DaprClient` constructor.
    """

    def __init__(
        self,
        dapr_http_port: Optional[int] = app_settings.dapr_http_port,
        dapr_api_token: Optional[str] = secrets_settings.dapr_api_token,
        api_method_invocation_protocol: Optional[str] = app_settings.dapr_api_method_invocation_protocol,
        health_timeout: Optional[int] = app_settings.dapr_health_timeout,
        **kwargs: Any,
    ):
        """Initialize the DaprService with optional API method invocation protocol and health timeout.

        Args:
            api_method_invocation_protocol (Optional[str]): The protocol for API method invocation.
            health_timeout (Optional[int]): Timeout for health checks.
            **kwargs: Additional keyword arguments for the `DaprClient` initialization.
        """
        settings_updates = {
            "DAPR_HTTP_PORT": dapr_http_port,
            "DAPR_API_TOKEN": dapr_api_token,
            "DAPR_API_METHOD_INVOCATION_PROTOCOL": api_method_invocation_protocol,
            "DAPR_HEALTH_TIMEOUT": health_timeout,
        }

        for attr, value in settings_updates.items():
            if value is not None:
                setattr(dapr_settings, attr, value)

        super().__init__(**kwargs)

    @SuppressAndLog(Exception, _logger=logger, default_return=({}, None))
    async def sync_configurations(
        self,
        keys: Union[str, List[str]],
        configstore_name: Optional[str] = app_settings.configstore_name,
        subscription_callback: Optional[Callable[[str, ConfigurationResponse], None]] = None,
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        """Sync configurations from the specified config store and optionally subscribe to configuration changes.

        Args:
            keys (str | List[str]): The configuration keys to sync.
            configstore_name (Optional[str]): The name of the configuration store. Defaults to `app_settings.configstore_name`.
            subscription_callback (Optional[Callable[[str, ConfigurationResponse], None]]): Optional callback
                function for handling configuration updates. If provided, will subscribe to configuration changes.

        Returns:
            Tuple[Dict[str, Any], Optional[str]]: A tuple containing a dictionary of configurations and an optional
            subscription ID. The dictionary maps keys to their corresponding configuration values.
        """
        config = {}
        if configstore_name:
            keys = [keys] if isinstance(keys, str) else keys
            try:
                configuration = self.get_configuration(store_name=configstore_name, keys=keys, config_metadata={})
                logger.info("Found %d/%d configurations, syncing...", len(configuration.items), len(keys))
                config = {key: configuration.items[key].value for key in configuration.items}
            except Exception as e:
                logger.exception("Failed to get configurations: %s", str(e))

        sub_id = None
        if configstore_name and subscription_callback is not None:
            try:
                # FIXME: subscription gets stopped with the following message when the app receives a request
                #  configstore configuration watcher for keys ['fastapi_soa.debug'] stopped.
                sub_id = self.subscribe_configuration(
                    store_name=configstore_name, keys=keys, handler=subscription_callback, config_metadata={}
                )
                logger.debug("Successfully subscribed to config store with subscription id: %s", sub_id)
            except Exception as e:
                logger.exception("Failed to subscribe to config store: %s", str(e))

        return config, sub_id

    @SuppressAndLog(Exception, _logger=logger, default_return={})
    async def sync_secrets(
        self,
        keys: Union[str, List[str]],
        secretstore_name: Optional[str] = app_settings.secretstore_name,
    ) -> Dict[str, Any]:
        """Sync secrets from the specified secret store.

        Args:
            keys (str | List[str]): The secret keys to sync.
            secretstore_name (str): The name of the secret store. Defaults to `app_settings.secretstore_name`.

        Returns:
            Dict[str, Any]: A dictionary of secrets where each key maps to its corresponding secret value.
        """
        secrets = {}
        if secretstore_name:
            keys = [keys] if isinstance(keys, str) else keys
            for key in keys:
                try:
                    secrets[key] = self.get_secret(store_name=secretstore_name, key=key).secret.get(key)
                except Exception as e:
                    logger.error("Failed to get secret: %s", str(e))

            logger.info("Found %d/%d secrets, syncing...", len(secrets), len(keys))

        return secrets

    async def unsync_configurations(self, configstore_name: str, sub_id: str) -> bool:
        """Unsubscribe from configuration updates and stop syncing.

        Args:
            configstore_name (str): The name of the configuration store.
            sub_id (str): The subscription ID to unsubscribe from.

        Returns:
            bool: True if successfully unsubscribed, False otherwise.
        """
        is_success = False

        if sub_id:
            try:
                is_success = self.unsubscribe_configuration(store_name=configstore_name, id=sub_id)
                logger.debug("Unsubscribed successfully? %s", is_success)
            except Exception as e:
                logger.exception("Failed to unsubscribe from config store: %s", str(e))

        return is_success

    async def publish_to_topic(
        self,
        pubsub_name: str,
        topic_name: str,
        data: Dict[str, Any],
        source: str = app_settings.name,
        event_type: Optional[str] = None,
    ) -> str:
        """Publish data to a specified pubsub topic.

        Args:
            pubsub_name (str): The name of the pubsub component.
            topic_name (str): The name of the topic to publish to.
            data (Dict[str, Any]): The data to publish.
            source (str, optional): The source of the event. Defaults to the value of `app_settings.name`.
            event_type (str, optional): The type of the event. If not provided, it will be omitted from the CloudEvent metadata.

        Returns:
            str: The ID of the published CloudEvent.

        Raises:
            DaprInternalError: If there's an error while publishing the event.

        Note:
            The data is published as a CloudEvent, with the content type set to 'application/cloudevents+json'.
        """
        event_id = str(uuid.uuid4())
        publish_metadata = {
            "cloudevent.id": event_id,
            "cloudevent.source": source,
            "cloudevent.type": event_type,
        }
        publish_metadata = {k: v for k, v in publish_metadata.items() if v is not None}
        data.update(
            {
                k: publish_metadata[f"cloudevent.{k}"]
                for k in ("source", "type")
                if f"cloudevent.{k}" in publish_metadata
            }
        )

        self.publish_event(
            pubsub_name=pubsub_name,
            topic_name=topic_name,
            data=json.dumps(data),
            data_content_type="application/cloudevents+json",
            publish_metadata=publish_metadata,
        )

        logger.debug("Published to pubsub topic %s/%s", pubsub_name, topic_name)
        return event_id
