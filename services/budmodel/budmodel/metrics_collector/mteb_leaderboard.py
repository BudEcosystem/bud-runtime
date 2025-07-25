import asyncio
from pyppeteer import launch
import json


async def get_table_rows():
    browser = await launch(headless=True, args=["--no-sandbox"])
    page = await browser.newPage()

    # Load the page and wait for content
    await page.goto(
        "https://mteb-leaderboard.hf.space/?__theme=light", {"waitUntil": "networkidle2", "timeout": 600000}
    )
    await page.waitForSelector(
        "#component-16 > div.svelte-1bvc1p0 > div > button > svelte-virtual-table-viewport > table > tbody"
    )

    # Define headers with underscores for database fields
    headers = [
        "rank",
        "model_name",
        "model_url",
        "model_size_million_parameters",
        "memory_usage_gb_fp32",
        "embedding_dimensions",
        "max_tokens",
        "average_56_datasets",
        "classification_average_12_datasets",
        "clustering_average_11_datasets",
        "pair_classification_average_3_datasets",
        "reranking_average_4_datasets",
        "retrieval_average_15_datasets",
        "sts_average_10_datasets",
        "summarization_average_1_datasets",
    ]

    # Store each row's data
    table_data = []
    rows = await page.querySelectorAll(
        "#component-16 > div.svelte-1bvc1p0 > div > button > svelte-virtual-table-viewport > table > tbody > tr"
    )

    for row in rows:
        cells = await row.querySelectorAll("td > div > span")
        cell_values = []

        for i, cell in enumerate(cells):
            if i == 1:  # Assuming the Model name is the second column
                model_link = await cell.querySelector("a")
                if model_link:
                    model_name = await page.evaluate("(element) => element.textContent", cell)
                    href = await page.evaluate("(element) => element.href", model_link)
                    cell_values.extend([model_name.strip(), href.strip()])
                else:
                    model_name = await page.evaluate("(element) => element.textContent", cell)
                    cell_values.extend([model_name.strip(), None])  # No URL
            else:
                cell_text = await page.evaluate("(element) => element.textContent", cell)
                cell_values.append(cell_text.strip())

        # Map headers to values
        row_data = {headers[i]: cell_values[i] for i in range(len(headers))}
        table_data.append(row_data)

    await browser.close()

    # Print JSON-formatted data
    print(json.dumps(table_data, indent=4))
    return table_data


# Run the async function
# asyncio.get_event_loop().run_until_complete(get_table_rows())
