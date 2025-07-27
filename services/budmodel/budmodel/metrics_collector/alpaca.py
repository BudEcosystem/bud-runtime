import json

from pyppeteer import launch


async def get_alpaca_eval_leaderboard():
    """Fetch leaderboard data from Alpaca Eval.

    Returns:
        Extracted leaderboard data from Alpaca Eval website.
    """
    browser = await launch(headless=True, args=["--no-sandbox"])
    page = await browser.newPage()
    await page.goto("https://tatsu-lab.github.io/alpaca_eval/", {"waitUntil": "networkidle2", "timeout": 600000})

    await page.waitForSelector("#leaderboard > tr")
    rows = await page.querySelectorAll("#leaderboard > tr")

    headers = ["rank", "model_name", "model_url", "lc_win_rate", "win_rate"]
    table_data = []

    for row in rows[1:]:  # Skip header row
        cells = await row.querySelectorAll("td")
        cell_values = []

        for i, cell in enumerate(cells):
            if i == 1:  # Assuming model name and URL are in the second column
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

        row_data = {headers[i]: cell_values[i] for i in range(len(headers))}
        table_data.append(row_data)

    await browser.close()
    print(json.dumps(table_data, indent=4))
    return table_data


# asyncio.get_event_loop().run_until_complete(get_alpaca_eval_leaderboard())
