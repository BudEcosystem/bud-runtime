import asyncio

from crawl4ai import AsyncWebCrawler
from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from pydantic import BaseModel, Field

from budmodel.commons.config import get_secrets_config


# Get API key from configuration
secrets = get_secrets_config()
API_KEY = secrets.openai_api_key


#
class OpenAIModelFee(BaseModel):
    model_name: str = Field(..., description="Name of the OpenAI model.")
    rank: int = Field(..., description="Rank of the model based on performance.")
    model_size: int = Field(..., description="Size of the model in million parameters.")
    memory_usage: float = Field(..., description="Memory usage in GB (fp32).")
    embedding_dimensions: int = Field(..., description="Number of embedding dimensions for the model.")
    max_tokens: int = Field(..., description="Maximum number of tokens allowed.")
    average_score: float = Field(..., description="Average score across datasets.")
    classification_average: float = Field(..., description="Classification average.")
    clustering_average: float = Field(..., description="Clustering average.")
    pair_classification_average: float = Field(..., description="Pair classification average.")
    reranking_average: float = Field(..., description="Reranking average.")
    retrieval_average: float = Field(..., description="Retrieval average.")
    sts_average: float = Field(..., description="STS (Semantic Textual Similarity) average.")
    summarization_average: float = Field(..., description="Summarization average.")
    url: str = Field(..., description="URL of the model.")


#
# async def crawl_huggingface_leaderboard():
#     async def on_execution_started(page):
#         try:
#             print("here____")
#             await page.wait_for_selector("#component-4")
#             # await page.sleep
#         except Exception as e:
#             print(f"Warning: New content didn't appear after JavaScript execution: {e}")
#
#     async with AsyncWebCrawler(verbose=True) as crawler:
#         crawler.crawler_strategy.set_hook('on_execution_started', on_execution_started)
#
#         url = "https://huggingface.co/spaces/mteb/leaderboard"
#         session_id = "huggingface_leaderboard_session"
#
#         result = await crawler.arun(
#             url=url,
#             session_id=session_id,
#             css_selector="#component-4",
#             bypass_cache=True,
#             extraction_strategy=LLMExtractionStrategy(
#                 provider="openai/gpt-4o",
#                 api_token=API_KEY,
#                 schema=OpenAIModelFee.schema(),
#                 extraction_type="schema",
#                 instruction="""Extract all models' names and metrics. Output as JSON:
#                 {
#                     "model_name": "GPT-4",
#                     "rank": 1,
#                     "model_size": 1750,
#                     "memory_usage": 280.3,
#                     "embedding_dimensions": 1024,
#                     "max_tokens": 4096,
#                     "average_score": 85.5,
#                     "classification_average": 89.2,
#                     "clustering_average": 83.4,
#                     "pair_classification_average": 87.0,
#                     "reranking_average": 86.1,
#                     "retrieval_average": 84.3,
#                     "sts_average": 88.0,
#                     "summarization_average": 90.5,
#                     "url": "https://model_url"
#                 }
#                 """
#             )
#         )
#
#         print(result)
#
#         assert result.success, "Failed to crawl the page"
#
#         # Process and print the results
#         soup = BeautifulSoup(result.cleaned_html, 'html.parser')
#         models = soup.select("tbody tr")  # Adjust if necessary to select individual rows in the table
#         print(f"Found {len(models)} models on the first page.")
#
#         await crawler.crawler_strategy.kill_session(session_id)
#
# if __name__ == "__main__":
#     asyncio.run(crawl_huggingface_leaderboard())


async def crawl_huggingface_leaderboard():
    """Crawl the Hugging Face leaderboard for model data."""
    print("here_______")
    # Wait function to ensure necessary content is loaded on the page
    wait_for = """
    () => {
        const tableContent = document.querySelectorAll('#component-4');
        return tableContent.length > 0; // Proceed once at least one row is detected
    }
    """

    async with AsyncWebCrawler(verbose=True, crawler_strategy=AsyncPlaywrightCrawlerStrategy()) as crawler:
        # Run the crawler with specific strategies and dynamic content loading
        result = await crawler.arun(
            url="https://huggingface.co/spaces/mteb/leaderboard",
            # js_code=js_code,
            wait_for=wait_for,
            css_selector="#component-4",  # Adjust to the actual element needed
            extraction_strategy=LLMExtractionStrategy(
                provider="openai/gpt-4o",
                api_token=API_KEY,
                schema=OpenAIModelFee.schema(),
                extraction_type="schema",
                instruction="""Extract all models' names and metrics. Each entry should look like this:
                {
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
                }
                """,
            ),
            # chunking_strategy=RegexChunking(),  # Optional, for splitting content efficiently
        )

    # Display the extracted structured result
    print(result.extracted_content)


# Run the async function
asyncio.run(crawl_huggingface_leaderboard())
