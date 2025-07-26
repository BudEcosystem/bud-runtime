import asyncio
import json

from pyppeteer import launch


async def get_arena_leaderboard():
    browser = await launch(headless=True, args=["--no-sandbox"])
    page = await browser.newPage()

    # Load the page and wait for content
    await page.goto(
        "https://lmarena-ai-chatbot-arena-leaderboard.hf.space/", {"waitUntil": "networkidle2", "timeout": 600000}
    )
    await page.waitForSelector(
        "#full_leaderboard_dataframe > div.svelte-1oa6fve > div > button > svelte-virtual-table-viewport > table > tbody"
    )

    # Define headers for database-ready format
    headers = [
        "model_name",
        "model_url",
        "arena_score",
        "arena_hard_auto",
        "mt_bench",
        "mmlu",
        "organization",
        "license",
    ]

    # Store each row's data
    table_data = []
    rows = await page.querySelectorAll(
        "#full_leaderboard_dataframe > div.svelte-1oa6fve > div > button > svelte-virtual-table-viewport > table > tbody > tr"
    )

    for row in rows:
        cells = await row.querySelectorAll("td > div > span")
        cell_values = []

        # Extract text content and URL for model name
        for i, cell in enumerate(cells):
            if i == 0:  # Assuming model name is the first column
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
asyncio.get_event_loop().run_until_complete(get_arena_leaderboard())
