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

"""The base class for leaderboard module."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Union

from .schemas import BaseCrawlerConfig


class BaseCrawler(ABC):
    """Base class for all crawlers."""

    def __init__(self, url: str):
        """Initialize the crawler.

        Args:
            url: Target URL to crawl
        """
        self.url = url

    @abstractmethod
    def build_config(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Build the config for the crawler.

        Args:
            kwargs: The kwargs to build the config.

        Returns:
            Dict[str, Any]: The built config.
        """
        pass

    @abstractmethod
    def extract_data(self, config: BaseCrawlerConfig) -> List[Dict[str, Any]]:
        """Extract data from the configured URL.

        Args:
            **kwargs: Configuration parameters for the crawler

        Returns:
            List[Dict[str, Any]]: The extracted data.

        Raises:
            CrawlerException: If extraction fails
        """
        pass


class BaseSourceParser(ABC):
    """Base class for all leaderboard parsers."""

    @abstractmethod
    async def parse_data(self, data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse the data from the source.

        Args:
            data: The data to parse.

        Returns:
            List[Dict[str, Any]]: The parsed data.
        """
        pass

    @abstractmethod
    async def parse_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the entry from the source.

        Args:
            entry: The entry to parse.

        Returns:
            Dict[str, Any]: The parsed entry.
        """
        pass
