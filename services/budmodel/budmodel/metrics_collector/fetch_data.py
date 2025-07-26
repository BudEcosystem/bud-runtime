import asyncio
import json

from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy


async def extract_data(url, schema, wait_for="", js_code="", css_base_selector=""):
    extraction_strategy = JsonCssExtractionStrategy(schema, verbose=True)

    async def on_execution_started_hook(page):
        print(f"Execution started on page: {page.url}")

    async with AsyncWebCrawler(verbose=True, headless=True) as crawler:
        crawler.crawler_strategy.set_hook("on_execution_started", on_execution_started_hook)
        print(wait_for)
        print(js_code)
        try:
            params = {
                "url": url,
                "extraction_strategy": extraction_strategy,
                "bypass_cache": True,
                "browser_type": "chromium",
                "page_timeout": 120000,
                "delay_before_return_html": 100,
            }
            #
            # if wait_for:
            #     params["wait_for"] = wait_for

            if js_code:
                params["js_code"] = [js_code]

            if css_base_selector:
                params["css_selector"] = css_base_selector

            result = await crawler.arun(**params)

            assert result.success, "Failed to crawl the page"
            with open("crawler_result.txt", "w") as file:
                file.write(str(result))

            data = json.loads(result.extracted_content)
            # print(json.dumps(data, indent=2))  # Print all extracted data
            print(f"Successfully extracted {len(data)} data entries.")
            return data

        except Exception as e:
            print("Error occurred:", e)
            return False


if __name__ == "__main__":
    asyncio.run(extract_data())
