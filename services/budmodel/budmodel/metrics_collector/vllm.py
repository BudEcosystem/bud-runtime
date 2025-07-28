import asyncio
import json

from pyppeteer import launch


async def get_vlm_leaderboard():
    """Fetch leaderboard data from VLM.

    Returns:
        Extracted leaderboard data from VLM website.
    """
    browser = await launch(headless=True, args=["--no-sandbox"])
    page = await browser.newPage()
    await page.goto(
        "https://opencompass-open-vlm-leaderboard.hf.space/?__theme=light",
        {"waitUntil": "networkidle2", "timeout": 600000},
    )

    # Scroll to load all rows
    previous_height = await page.evaluate("() => document.body.scrollHeight")
    while True:
        await page.evaluate("window.scrollBy(0, window.innerHeight);")
        await asyncio.sleep(2)  # Adjust delay as needed
        new_height = await page.evaluate("() => document.body.scrollHeight")
        if new_height == previous_height:
            break
        previous_height = new_height

    await page.waitForSelector(
        "#component-10 > div.svelte-1bvc1p0 > div > button > svelte-virtual-table-viewport > table > tbody"
    )
    rows = await page.querySelectorAll(
        "#component-10 > div.svelte-1bvc1p0 > div > button > svelte-virtual-table-viewport > table > tbody > tr"
    )

    headers = ["rank", "method", "param_b", "language_model", "vision_model"]
    table_data = []

    for row in rows:
        cells = await row.querySelectorAll("td span")
        cell_values = []

        for i, cell in enumerate(cells):
            if i == 1:
                method_link = await cell.querySelector("a")
                if method_link:
                    method_name = await page.evaluate("(element) => element.textContent", cell)
                    href = await page.evaluate("(element) => element.href", method_link)
                    cell_values.extend([method_name.strip(), href.strip()])
                else:
                    method_name = await page.evaluate("(element) => element.textContent", cell)
                    cell_values.extend([method_name.strip(), None])
            else:
                cell_text = await page.evaluate("(element) => element.textContent", cell)
                cell_values.append(cell_text.strip())

        row_data = {headers[i]: cell_values[i] for i in range(len(headers))}
        table_data.append(row_data)

    await browser.close()
    print(json.dumps(table_data, indent=4))


asyncio.get_event_loop().run_until_complete(get_vlm_leaderboard())
