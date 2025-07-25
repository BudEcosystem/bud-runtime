import asyncio
from pyppeteer import launch
import json


async def get_livecodebench_leaderboard():
    browser = await launch(headless=True, args=["--no-sandbox"])
    page = await browser.newPage()
    await page.goto(
        "https://livecodebench.github.io/leaderboard.html", {"waitUntil": "networkidle2", "timeout": 600000}
    )

    # Wait an extended time to ensure all rows are fully loaded
    await asyncio.sleep(10)

    # Extract rows
    rows = await page.querySelectorAll("div[role='row']")

    headers = ["rank", "model_name", "model_url", "pass", "easy_pass", "medium_pass"]
    table_data = []

    for row in rows:
        cells = await row.querySelectorAll("div[role='gridcell'] .ag-cell-value")
        cell_values = []

        if len(cells) > 0:
            rank = await page.evaluate("(element) => element.textContent", cells[0])
            if rank.strip():  # Only include rows with a non-empty rank
                for i in range(len(headers)):
                    if i < len(cells):
                        cell = cells[i]
                        if i == 1:
                            model_link = await cell.querySelector("a")
                            if model_link:
                                model_name = await page.evaluate("(element) => element.textContent", cell)
                                href = await page.evaluate("(element) => element.href", model_link)
                                cell_values.extend([model_name.strip(), href.strip()])
                            else:
                                model_name = await page.evaluate("(element) => element.textContent", cell)
                                cell_values.extend([model_name.strip(), None])
                        else:
                            cell_text = await page.evaluate("(element) => element.textContent", cell)
                            cell_values.append(cell_text.strip())
                    else:
                        cell_values.append(None)

                row_data = {headers[i]: cell_values[i] for i in range(len(headers))}
                table_data.append(row_data)

    await browser.close()
    print(json.dumps(table_data, indent=4))
    print(f"Total rows extracted: {len(table_data)}")
    return table_data


# Run the async function
# asyncio.get_event_loop().run_until_complete(get_livecodebench_leaderboard())
