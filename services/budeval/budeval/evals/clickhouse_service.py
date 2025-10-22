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

"""Simplified ClickHouse database service for managing connections."""

import asyncio
from typing import Optional

import clickhouse_connect
from clickhouse_connect.driver.asyncclient import AsyncClient
from clickhouse_connect.driver.client import Client

from budeval.commons.config import app_settings
from budeval.commons.logging import logging


logger = logging.getLogger(__name__)


class ClickHouseService:
    """Simplified service for managing ClickHouse database connections."""

    _instance: Optional["ClickHouseService"] = None
    _client: Optional[Client] = None
    _async_client: Optional[AsyncClient] = None
    _lock = asyncio.Lock()

    def __new__(cls) -> "ClickHouseService":
        """Implement singleton pattern for ClickHouseService."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def connect(self) -> Client:
        """Establish synchronous connection to ClickHouse.

        Returns:
            ClickHouse client instance

        Raises:
            Exception: If connection fails
        """
        if self._client is None:
            try:
                logger.info("Establishing ClickHouse connection...")
                self._client = clickhouse_connect.get_client(
                    host=app_settings.clickhouse_host,
                    port=app_settings.clickhouse_http_port,
                    database=app_settings.clickhouse_database,
                    username=app_settings.clickhouse_user,
                    password=app_settings.clickhouse_password,
                    secure=app_settings.clickhouse_secure,
                )

                # Test connection
                self._client.query("SELECT 1")
                logger.info("ClickHouse connection successful")

            except Exception as e:
                logger.error(f"Failed to connect to ClickHouse: {e}")
                self._client = None
                raise

        return self._client

    async def connect_async(self) -> AsyncClient:
        """Establish asynchronous connection to ClickHouse.

        Returns:
            Async ClickHouse client instance

        Raises:
            Exception: If connection fails
        """
        async with self._lock:
            if self._async_client is None:
                try:
                    logger.info("Establishing async ClickHouse connection...")
                    self._async_client = await clickhouse_connect.get_async_client(
                        host=app_settings.clickhouse_host,
                        port=app_settings.clickhouse_http_port,
                        database=app_settings.clickhouse_database,
                        username=app_settings.clickhouse_user,
                        password=app_settings.clickhouse_password,
                        secure=app_settings.clickhouse_secure,
                    )

                    # Test connection
                    await self._async_client.query("SELECT 1")
                    logger.info("Async ClickHouse connection successful")

                except Exception as e:
                    logger.error(f"Failed to connect to async ClickHouse: {e}")
                    self._async_client = None
                    raise

        return self._async_client

    def disconnect(self) -> None:
        """Close synchronous ClickHouse connection."""
        if self._client:
            try:
                self._client.close()
                self._client = None
                logger.info("ClickHouse connection closed")
            except Exception as e:
                logger.error(f"Error closing ClickHouse connection: {e}")

    async def disconnect_async(self) -> None:
        """Close asynchronous ClickHouse connection."""
        if self._async_client:
            try:
                await self._async_client.close()
                self._async_client = None
                logger.info("Async ClickHouse connection closed")
            except Exception as e:
                logger.error(f"Error closing async ClickHouse connection: {e}")

    def get_client(self) -> Optional[Client]:
        """Get the current synchronous client instance.

        Returns:
            Client instance if connected, None otherwise
        """
        return self._client

    def get_async_client(self) -> Optional[AsyncClient]:
        """Get the current asynchronous client instance.

        Returns:
            AsyncClient instance if connected, None otherwise
        """
        return self._async_client

    def is_connected(self) -> bool:
        """Check if synchronous client is connected.

        Returns:
            True if connected, False otherwise
        """
        return self._client is not None

    def is_async_connected(self) -> bool:
        """Check if asynchronous client is connected.

        Returns:
            True if connected, False otherwise
        """
        return self._async_client is not None


# Singleton instance
clickhouse_service = ClickHouseService()
