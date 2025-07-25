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

"""The web crawler for leaderboard."""

import json
from typing import Any, Dict, List

from budmicroframe.commons import logging
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

from ..commons.constants import CrawlerType
from ..commons.exceptions import CrawlerException
from .base import BaseCrawler
from .schemas import Crawl4aiConfig


logger = logging.get_logger(__name__)


class Crawl4aiCrawler(BaseCrawler):
    """Crawler4ai crawler."""

    def __init__(self, url: str) -> None:
        """Initialize the Crawl4aiCrawler.

        Args:
            url (str): The URL to crawl.
        """
        super().__init__(url)

    def build_config(self, config: Crawl4aiConfig) -> Dict[str, Any]:
        """Build the config for the crawler4ai crawler.

        Args:
            config (Crawl4aiConfig): The config to build.

        Returns:
            dict: The built config.
        """
        # Convert config to dict
        config = config.model_dump()

        # Add url to config
        config["url"] = self.url

        # Add extraction strategy to config
        config["extraction_strategy"] = JsonCssExtractionStrategy(config["schema"], verbose=True)

        return config

    async def extract_data(self, config: Crawl4aiConfig) -> List[Dict[str, Any]]:
        """Extract data from the target URL.

        Args:
            config (Crawl4aiConfig): The config to validate.

        Returns:
            List[Dict[str, Any]]: The extracted data.
        """
        # Build the config
        config = self.build_config(config)

        # Run the crawler
        async with AsyncWebCrawler(verbose=True, headless=True) as crawler:
            logger.debug("Crawling the page %s", self.url)
            result = await crawler.arun(**config)

        # Check if the result is successful
        if not result.success:
            raise CrawlerException("Failed to crawl the page")

        # Return the extracted data
        return json.loads(result.extracted_content)


class CrawlerFactory:
    """Factory class to create different types of crawlers."""

    _crawlers = {
        CrawlerType.CRAWL4AI: Crawl4aiCrawler,
    }

    @classmethod
    def get_crawler(cls, crawler_type: CrawlerType, url: str) -> BaseCrawler:
        """Get a crawler instance based on the crawler type.

        Args:
            crawler_type (CrawlerType): The type of crawler to create.
            url (str): The URL to crawl.

        Returns:
            BaseCrawler: An instance of the specified crawler type.

        Raises:
            ValueError: If the specified crawler type is not supported.
        """
        crawler_class = cls._crawlers.get(crawler_type)
        if not crawler_class:
            raise CrawlerException(f"Unsupported crawler type: {crawler_type}")
        return crawler_class(url)
