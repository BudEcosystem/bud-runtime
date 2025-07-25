from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import LLMExtractionStrategy
import openai
import json5

from budmodel.commons.config import get_secrets_config

# Set up headless Chrome options
options = Options()
options.headless = True  # Enable headless mode
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--enable-javascript")
options.add_argument("--disable-web-security")
options.add_argument("--allow-running-insecure-content")

# options.add_argument("--headless=new")


# Initialize WebDriver
driver = webdriver.Chrome(options=options)
driver.get_log("browser")


try:
    # Open the target URL
    driver.get("https://huggingface.co/spaces/mteb/leaderboard")  # Replace with your URL

    # Define a timeout
    timeout = 50  # 10 seconds

    # Wait for the element with the selector #component-11
    try:
        # WebDriverWait(driver, timeout).until(
        #     lambda d: d.execute_script("return document.readyState") == "complete"
        # )
        time.sleep(5)
        # element = WebDriverWait(driver, timeout).until(
        #     EC.presence_of_element_located((By.CSS_SELECTOR, "#component-11"))
        # )

        for _ in range(50):  # Retry up to 50 times (roughly 50 seconds if you sleep 1 second each time)
            element = driver.execute_script("return document.querySelector('#component-11');")
            if element:
                break
            time.sleep(1)
        else:
            print("Element #component-11 not found.")

        print("Element #component-11 found!")

        # Get the page HTML after the element is present
        page_html = driver.page_source
        # print(page_html)

        prompt = f"""
        Extract all models' names and metrics from the HTML content. Output in the following JSON format:
        [
            {{
                "model_name": "GPT-4",
                "rank": 1,
                "model_size": 1750,
                "memory_usage": 280.3,
                "embedding_dimensions": 1024,
                "max_tokens": 4096,
                "average_score": 85.5,
                "classification_average": 89.2,
                "clustering_average": 83.4,
                "pair_classification_average": 87.0,
                "reranking_average": 86.1,
                "retrieval_average": 84.3,
                "sts_average": 88.0,
                "summarization_average": 90.5,
                "url": "https://model_url"
            }},
            ...
        ]

        HTML content:
        {page_html}
        """

        # Get API key from configuration
        secrets = get_secrets_config()
        openai.api_key = secrets.openai_api_key

        # Define the prompt and HTML content

        # Make the OpenAI API call
        # response = openai.chat.completions.create(
        #     model="gpt-4-turbo",
        #     messages=[{"role": "user", "content": prompt}]
        # )
        #
        # print(response)
        # # Use json5 to parse the response content
        # response_content = response['choices'][0]['message']['content']
        #
        # try:
        #     extracted_data = json5.loads(response_content)
        #     print(extracted_data)  # JSON output from json5
        # except json5.JSONDecodeError:
        #     print("Failed to parse JSON5 format. Response:", response_content)
        # Use asyncio to run the extraction

    except TimeoutException:
        print(f"Element #component-11 not found within {timeout} seconds.")

finally:
    # Close the browser
    driver.quit()