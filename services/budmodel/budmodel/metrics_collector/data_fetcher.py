import asyncio
import json

from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy


async def extract_data():
    """Extract leaderboard data from web page using CSS selectors."""
    # Define the extraction schema to target the new container
    schema = {
        "name": "leaderboard",
        "baseSelector": ".model-row",
        "fields": [
            {"name": "rank_ub", "selector": ".rank-ub", "type": "text"},
            {"name": "rank_style_ctrl", "selector": ".rank-style-ctrl", "type": "text"},
            {"name": "model_name", "selector": ".model-name a", "type": "text"},
            {"name": "model_url", "selector": ".model-name a", "type": "attribute", "attribute": "href"},
            {"name": "arena_score", "selector": ".arena-score", "type": "text"},
            {"name": "confidence_interval", "selector": ".confidence-interval", "type": "text"},
            {"name": "votes", "selector": ".votes", "type": "text"},
            {"name": "organization", "selector": ".organization", "type": "text"},
            {"name": "license", "selector": ".license", "type": "text"},
            {"name": "knowledge_cutoff", "selector": ".knowledge-cutoff", "type": "text"},
        ],
    }

    extraction_strategy = JsonCssExtractionStrategy(schema, verbose=True)

    wait_for = """
    () => {
    const table = document.querySelector('svelte-virtual-table-viewport table');
    if (table && table.querySelectorAll('tr[slot="tbody"]').length > 10) {
        console.log("Table loaded with sufficient rows.");
        return true;
    } else {
        console.log("Waiting for table rows to load...");
        return false;
    }
};
    """

    js_code = [
        """
      (function checkTableBody() {
    const potentialTableClasses = [
        '.table.svelte-82jkx',
        '.svelte-1oa6fve.fixed-layout',
        'svelte-virtual-table-viewport table',
        '.svelte-1oa6fve'
    ];

    let tableBody;
    for (const tableClass of potentialTableClasses) {
        tableBody = document.querySelector(tableClass);
        if (tableBody) break;
    }

    console.log("Checking for table body...", tableBody);

    if (tableBody) {
        console.log("tableBody found", tableBody);
        const collectedData = [];

        // Create or select the results container
        let resultsContainer = document.querySelector('.results-container');
        if (!resultsContainer) {
            resultsContainer = document.createElement('div');
            resultsContainer.classList.add('results-container');
            document.body.appendChild(resultsContainer);
        }

        function extractData() {
            const rows = tableBody.querySelectorAll('tr[slot="tbody"]');
            rows.forEach(row => {
                const cells = row.querySelectorAll('td');
                const modelName = cells[2]?.querySelector('a')?.innerText.trim() || '';

                if (!collectedData.some(data => data.model_name === modelName)) {
                    const rowData = {
                        rank_ub: cells[0]?.innerText.trim() || '',
                        rank_style_ctrl: cells[1]?.innerText.trim() || '',
                        model_name: modelName,
                        model_url: cells[2]?.querySelector('a')?.href || '',
                        arena_score: cells[3]?.innerText.trim() || '',
                        confidence_interval: cells[4]?.innerText.trim() || '',
                        votes: cells[5]?.innerText.trim() || '',
                        organization: cells[6]?.innerText.trim() || '',
                        license: cells[7]?.innerText.trim() || '',
                        knowledge_cutoff: cells[8]?.innerText.trim() || ''
                    };
                    collectedData.push(rowData);
                }
            });
        }

        let scrollAttempts = 0;

        function scrollTableBody() {
            const viewport = tableBody;
            tableBody.scrollTop += 300;

            setTimeout(() => {
                const newScrollHeight = viewport.scrollHeight;

                if (viewport.scrollTop + viewport.clientHeight >= newScrollHeight || scrollAttempts > 1000) {
                    console.log("Reached the end or max attempts, stopping scroll.");
                    extractData();
                    updateResultsContainer();
                } else {
                    console.log("Continuing to scroll...");
                    extractData();
                    scrollAttempts++;
                    scrollTableBody();
                }
            }, 500);
        }

        function updateResultsContainer() {
            resultsContainer.innerHTML = '';
            console.log("Total records:", collectedData.length);
            collectedData.forEach(rowData => {
                const row = document.createElement('div');
                row.classList.add('model-row');
                row.innerHTML = `
                    <div class="rank-ub">${rowData.rank_ub}</div>
                    <div class="rank-style-ctrl">${rowData.rank_style_ctrl}</div>
                    <div class="model-name"><a href="${rowData.model_url}" target="_blank">${rowData.model_name}</a></div>
                    <div class="arena-score">${rowData.arena_score}</div>
                    <div class="confidence-interval">${rowData.confidence_interval}</div>
                    <div class="votes">${rowData.votes}</div>
                    <div class="organization">${rowData.organization}</div>
                    <div class="license">${rowData.license}</div>
                    <div class="knowledge-cutoff">${rowData.knowledge_cutoff}</div>
                `;
                resultsContainer.appendChild(row);
            });
            console.log("Data appended to results container.");
        }

        extractData();
        scrollTableBody();

    } else {
        console.log("Table body not found, retrying in 500 ms...");
        setTimeout(checkTableBody, 500);
    }
})();

        """
    ]

    async def on_execution_started_hook(page):
        print(f"Execution started on page: {page.url}")

    async with AsyncWebCrawler(verbose=True, headless=False) as crawler:
        crawler.crawler_strategy.set_hook("on_execution_started", on_execution_started_hook)

        try:
            result = await crawler.arun(
                url="https://lmarena-ai-chatbot-arena-leaderboard.hf.space/",
                extraction_strategy=extraction_strategy,
                bypass_cache=True,
                headless=False,
                browser_type="chromium",
                wait_for=wait_for,
                # css_selector="svelte-virtual-table-viewport table",
                page_timeout=120000,
                js_code=js_code,
                delay_before_return_html=100,
            )

            assert result.success, "Failed to crawl the page"
            with open("crawler_result.txt", "w") as file:
                file.write(str(result))

            data = json.loads(result.extracted_content)
            print(json.dumps(data, indent=2))  # Print all extracted data
            print(f"Successfully extracted {len(data)} data entries.")

        except Exception as e:
            print("Error occurred:", e)


if __name__ == "__main__":
    asyncio.run(extract_data())
