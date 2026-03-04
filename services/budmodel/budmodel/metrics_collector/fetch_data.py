import asyncio
import json

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, JsonCssExtractionStrategy


async def extract_data(url, schema, wait_for="", js_code="", css_base_selector=""):
    """Extract data from web page using provided schema and configuration.

    Args:
        url: Target URL to crawl.
        schema: Extraction schema for CSS selectors.
        wait_for: CSS selector to wait for before extraction.
        js_code: JavaScript code to execute on page.
        css_base_selector: Base CSS selector for extraction.

    Returns:
        Extracted data in JSON format.
    """
    extraction_strategy = JsonCssExtractionStrategy(schema)

    browser_config = BrowserConfig(headless=True, browser_type="chromium")
    async with AsyncWebCrawler(config=browser_config) as crawler:
        print(wait_for)
        print(js_code)
        try:
            run_params = {
                "extraction_strategy": extraction_strategy,
                "bypass_cache": True,
                "page_timeout": 120000,
                "delay_before_return_html": 100,
            }

            if js_code:
                run_params["js_code"] = [js_code]

            if css_base_selector:
                run_params["css_selector"] = css_base_selector

            run_config = CrawlerRunConfig(**run_params)
            result = await crawler.arun(url=url, config=run_config)

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
