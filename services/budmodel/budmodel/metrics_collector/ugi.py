import asyncio
import json

from pyppeteer import launch


async def get_ugi_leaderboard():
    browser = await launch(headless=True, args=["--no-sandbox"])
    page = await browser.newPage()
    await page.goto(
        "https://dontplantoend-ugi-leaderboard.hf.space/?__theme=light",
        {"waitUntil": "networkidle2", "timeout": 600000},
    )
    await asyncio.sleep(5)
    # Scroll to load all rows
    previous_height = await page.evaluate("() => document.body.scrollHeight")
    while True:
        await page.evaluate("window.scrollBy(0, window.innerHeight);")
        await asyncio.sleep(2)
        new_height = await page.evaluate("() => document.body.scrollHeight")
        if new_height == previous_height:
            break
        previous_height = new_height

    # Retry loop to wait for tbody > tr elements
    for _ in range(20):  # Up to 20 attempts
        rows = await page.querySelectorAll(
            "#component-21 > div.svelte-1bvc1p0 > div > button > svelte-virtual-table-viewport > table > tbody > tr"
        )
        if rows:
            break
        await asyncio.sleep(3)  # Wait 3 seconds before retrying
    else:
        print("Rows did not load in time.")
        await browser.close()
        return

    headers = ["rank", "model", "ugi_score", "w_10", "i_10", "unruly", "internet", "stats", "writing", "polcontro"]
    table_data = []

    for row in rows:
        cells = await row.querySelectorAll("td span")
        cell_values = []

        for i, cell in enumerate(cells):
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

        row_data = {headers[i]: cell_values[i] for i in range(len(headers))}
        table_data.append(row_data)

    await browser.close()
    print(json.dumps(table_data, indent=4))


asyncio.get_event_loop().run_until_complete(get_ugi_leaderboard())
