import json

from pyppeteer import launch


async def get_gorilla_leaderboard():
    browser = await launch(headless=True, args=["--no-sandbox"])
    page = await browser.newPage()
    await page.goto(
        "https://gorilla.cs.berkeley.edu/leaderboard.html", {"waitUntil": "networkidle2", "timeout": 600000}
    )

    await page.waitForSelector("#leaderboard-table > tbody > tr")
    rows = await page.querySelectorAll("#leaderboard-table > tbody > tr")

    headers = [
        "rank",
        "overall_acc",
        "model_name",
        "model_url",
        "latency_cost",
        "latency_mean",
        "latency_sd",
        "latency_p95",
        "nonlive_ast_summary_simple",
        "nonlive_ast_summary_multiple",
        "nonlive_ast_summary_parallel",
        "nonlive_ast_summary_multiple_parallel",
        "nonlive_exec_summary_simple",
        "nonlive_exec_summary_multiple",
        "nonlive_exec_summary_parallel",
        "nonlive_exec_summary_multiple_parallel",
        "live_ast_overall_acc_simple",
        "live_ast_overall_acc_multiple",
        "live_ast_overall_acc_parallel",
        "live_ast_overall_acc_multiple_parallel",
        "multi_turn_overall_acc_base",
        "multi_turn_overall_acc_miss_func",
        "multi_turn_overall_acc_miss_param",
        "multi_turn_overall_acc_long_context",
        "multi_turn_overall_acc_composite",
        "halucination_relevance",
        "halucination_irrelevance",
        "organization",
        "license",
    ]

    table_data = []

    for row in rows:
        cells = await row.querySelectorAll("td")
        cell_values = []

        for i, cell in enumerate(cells):
            if i == 2:  # Assuming model name and URL are in the third column
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


# asyncio.get_event_loop().run_until_complete(get_gorilla_leaderboard())
