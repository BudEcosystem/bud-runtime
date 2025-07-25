sources = {
    "apac_eval": {
        "schema": {
            "name": "leaderboard",
            "baseSelector": "#leaderboard tr",
            "fields": [
                {"name": "rank", "selector": "td.rank", "type": "text"},
                {"name": "name", "selector": "td.name", "type": "text"},
                {"name": "url", "selector": "td.name a", "type": "attribute", "attribute": "href"},
                {"name": "lc_win_rate", "selector": "td.lenWinRate", "type": "text"},
                {"name": "win_rate", "selector": "td.winRate", "type": "text"},
            ],
        },
        "url": "https://tatsu-lab.github.io/alpaca_eval/",
        "baseSelector": "#leaderboard tr",
        "name": "APAC Eval Leaderboard",
        "js_code": None,
        "wait_for": None,
    },
    "berkeley": {
        "schema": {
            "name": "leaderboard",
            "baseSelector": "#leaderboard-table tbody tr",
            "fields": [
                {"name": "rank", "selector": "td:nth-child(1)", "type": "text"},
                {"name": "overall_accuracy", "selector": "td:nth-child(2)", "type": "text"},
                {
                    "name": "name",
                    "selector": "td:nth-child(3)",
                    "type": "text",
                },
                {
                    "name": "url",
                    "selector": "td:nth-child(3) a",
                    "type": "attribute",
                    "attribute": "href",
                },
                {
                    "name": "latency_cost",
                    "selector": "td:nth-child(4)",
                    "type": "text",
                },
                {
                    "name": "latency_mean",
                    "selector": "td:nth-child(5)",
                    "type": "text",
                },
                {
                    "name": "latency_sd",
                    "selector": "td:nth-child(6)",
                    "type": "text",
                },
                {
                    "name": "latency_p95",
                    "selector": "td:nth-child(7)",
                    "type": "text",
                },
                {
                    "name": "single_turn_non_live_ast_summary",
                    "selector": "td:nth-child(8)",
                    "type": "text",
                },
                {
                    "name": "single_turn_non_live_ast_simple",
                    "selector": "td:nth-child(9)",
                    "type": "text",
                },
                {
                    "name": "single_turn_non_live_ast_multiple",
                    "selector": "td:nth-child(10)",
                    "type": "text",
                },
                {
                    "name": "single_turn_non_live_ast_parallel",
                    "selector": "td:nth-child(11)",
                    "type": "text",
                },
                {
                    "name": "single_turn_non_live_ast_multiple_parallel",
                    "selector": "td:nth-child(12)",
                    "type": "text",
                },
                {
                    "name": "single_turn_non_live_exe_summary",
                    "selector": "td:nth-child(13)",
                    "type": "text",
                },
                {
                    "name": "single_turn_non_live_exe_simple",
                    "selector": "td:nth-child(14)",
                    "type": "text",
                },
                {
                    "name": "single_turn_non_live_exe_multiple",
                    "selector": "td:nth-child(15)",
                    "type": "text",
                },
                {
                    "name": "single_turn_non_live_exe_parallel",
                    "selector": "td:nth-child(16)",
                    "type": "text",
                },
                {
                    "name": "single_turn_non_live_exe_multiple_parallel",
                    "selector": "td:nth-child(17)",
                    "type": "text",
                },
                {
                    "name": "single_turn_live_ast_summary",
                    "selector": "td:nth-child(18)",
                    "type": "text",
                },
                {
                    "name": "single_turn_live_ast_simple",
                    "selector": "td:nth-child(19)",
                    "type": "text",
                },
                {
                    "name": "single_turn_live_ast_multiple",
                    "selector": "td:nth-child(20)",
                    "type": "text",
                },
                {
                    "name": "single_turn_live_ast_parallel",
                    "selector": "td:nth-child(21)",
                    "type": "text",
                },
                {
                    "name": "single_turn_live_ast_multiple_parallel",
                    "selector": "td:nth-child(22)",
                    "type": "text",
                },
                {
                    "name": "multi_turn_overall_accuracy",
                    "selector": "td:nth-child(23)",
                    "type": "text",
                },
                {
                    "name": "multi_turn_base",
                    "selector": "td:nth-child(24)",
                    "type": "text",
                },
                {
                    "name": "multi_miss_func",
                    "selector": "td:nth-child(25)",
                    "type": "text",
                },
                {
                    "name": "multi_miss_param",
                    "selector": "td:nth-child(26)",
                    "type": "text",
                },
                {
                    "name": "multi_long_context",
                    "selector": "td:nth-child(27)",
                    "type": "text",
                },
                {
                    "name": "multi_composite",
                    "selector": "td:nth-child(28)",
                    "type": "text",
                },
                {
                    "name": "hallucination_measurement_relevance",
                    "selector": "td:nth-child(29)",
                    "type": "text",
                },
                {
                    "name": "hallucination_measurement_irrelevance",
                    "selector": "td:nth-child(30)",
                    "type": "text",
                },
                {
                    "name": "organization",
                    "selector": "td:nth-child(31)",
                    "type": "text",
                },
                {
                    "name": "license",
                    "selector": "td:nth-child(32)",
                    "type": "text",
                },
            ],
        },
        "url": "https://gorilla.cs.berkeley.edu/leaderboard.html",
        "baseSelector": "#leaderboard-table tbody tr",
        "name": "Berkeley Leaderboard",
        "js_code": None,
        "wait_for": None,
    },
    "live_codebench": {
        "schema": {
            "name": "leaderboard",
            "baseSelector": "div[role='row']",
            "fields": [
                {"name": "rank", "selector": "div[col-id='Rank'][role='gridcell']", "type": "text"},
                {"name": "name", "selector": "div[col-id='Model'][role='gridcell']", "type": "text"},
                {
                    "name": "url",
                    "selector": "div[col-id='Model'][role='gridcell'] a",
                    "type": "attribute",
                    "attribute": "href",
                },
                {"name": "pass_1", "selector": "div[col-id='Pass@1'][role='gridcell']", "type": "text"},
                {"name": "easy_pass_1", "selector": "div[col-id='Easy-Pass@1'][role='gridcell']", "type": "text"},
                {"name": "medium_pass_1", "selector": "div[col-id='Medium-Pass@1'][role='gridcell']", "type": "text"},
                {"name": "hard_pass_1", "selector": "div[col-id='Hard-Pass@1'][role='gridcell']", "type": "text"},
            ],
        },
        "url": "https://livecodebench.github.io/leaderboard.html",
        "baseSelector": "div[role='row']",
        "name": "Live codebench Leaderboard",
        "js_code": None,
        "wait_for": None,
    },
    "mteb": {
        "schema": {
            "name": "leaderboard",
            "baseSelector": ".model-row",
            "fields": [
                {"name": "rank", "selector": "  .model-rank", "type": "text"},
                {"name": "name", "selector": "  .model-name", "type": "text"},
                {"name": "url", "selector": "  .model-url a", "type": "attribute", "attribute": "href"},
                {"name": "model_size_million_parameters", "selector": "  .model-size", "type": "text"},
                {"name": "memory_usage_gb_fp32", "selector": "  .memory-usage", "type": "text"},
                {"name": "embedding_dimensions", "selector": "  .embedding-dimensions", "type": "text"},
                {"name": "max_tokens", "selector": "  .max-tokens", "type": "text"},
                {"name": "average_56_datasets", "selector": "  .average-56-datasets", "type": "text"},
                {
                    "name": "classification_average_12_datasets",
                    "selector": "  .classification-average-12-datasets",
                    "type": "text",
                },
                {
                    "name": "clustering_average_11_datasets",
                    "selector": "  .clustering-average-11-datasets",
                    "type": "text",
                },
                {
                    "name": "pair_classification_average_3_datasets",
                    "selector": "  .pair-classification-average-3-datasets",
                    "type": "text",
                },
                {
                    "name": "reranking_average_4_datasets",
                    "selector": "  .reranking-average-4-datasets",
                    "type": "text",
                },
                {
                    "name": "retrieval_average_15_datasets",
                    "selector": "  .retrieval-average-15-datasets",
                    "type": "text",
                },
                {"name": "sts_average_10_datasets", "selector": "  .sts-average-10-datasets", "type": "text"},
                {
                    "name": "summarization_average_1_datasets",
                    "selector": "  .summarization-average-1-datasets",
                    "type": "text",
                },
            ],
        },
        "wait_for": """
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
    """,
        "js_code": [
            """
            (function checkTableBody() {
                const tableBody = document.querySelector('svelte-virtual-table-viewport table');
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
                            const modelName = cells[1]?.innerText.trim() || '';
    
                            if (!collectedData.some(data => data.model_name === modelName)) {
                                const rowData = {
                                    rank: cells[0]?.innerText.trim() || '',
                                    model_name: modelName,
                                    model_url: cells[1]?.querySelector('a')?.href || '',
                                    model_size_million_parameters: cells[2]?.innerText.trim() || '',
                                    memory_usage_gb_fp32: cells[3]?.innerText.trim() || '',
                                    embedding_dimensions: cells[4]?.innerText.trim() || '',
                                    max_tokens: cells[5]?.innerText.trim() || '',
                                    average_56_datasets: cells[6]?.innerText.trim() || '',
                                    classification_average_12_datasets: cells[7]?.innerText.trim() || '',
                                    clustering_average_11_datasets: cells[8]?.innerText.trim() || '',
                                    pair_classification_average_3_datasets: cells[9]?.innerText.trim() || '',
                                    reranking_average_4_datasets: cells[10]?.innerText.trim() || '',
                                    retrieval_average_15_datasets: cells[11]?.innerText.trim() || '',
                                    sts_average_10_datasets: cells[12]?.innerText.trim() || '',
                                    summarization_average_1_datasets: cells[13]?.innerText.trim() || ''
                                };
                                collectedData.push(rowData);
                            }
                        });
                    }
    
                    let scrollAttempts = 0;
    
                    function scrollTableBody() {
                        tableBody.scrollTop += 300;
    
                        setTimeout(() => {
                            const newScrollHeight = tableBody.scrollHeight;
    
                            if (tableBody.scrollTop + tableBody.clientHeight >= newScrollHeight || scrollAttempts > 1000) {
                                console.log("Reached the end or max attempts, stopping scroll.");
                                extractData(); // Final extraction in case of remaining items
                                updateResultsContainer(); // Append extracted data to results container
                            } else {
                                console.log("Continuing to scroll...");
                                extractData();
                                scrollAttempts++;
                                scrollTableBody(); // Recursive call to keep scrolling
                            }
                        }, 500);
                    }
    
                    function updateResultsContainer() {
                        resultsContainer.innerHTML = ''; // Clear existing content
    
                        collectedData.forEach(rowData => {
                            const row = document.createElement('div');
                            row.classList.add('model-row');
                            row.innerHTML = `
                                <div class="model-rank">${rowData.rank}</div>
                                <div class="model-name"><a href="${rowData.model_url}" target="_blank">${rowData.model_name}</a></div>
                                <div class="model-size">${rowData.model_size_million_parameters}</div>
                                <div class="memory-usage">${rowData.memory_usage_gb_fp32}</div>
                                <div class="embedding-dimensions">${rowData.embedding_dimensions}</div>
                                <div class="max-tokens">${rowData.max_tokens}</div>
                                <div class="average-56-datasets">${rowData.average_56_datasets}</div>
                                <div class="classification-average-12-datasets">${rowData.classification_average_12_datasets}</div>
                                <div class="clustering-average-11-datasets">${rowData.clustering_average_11_datasets}</div>
                                <div class="pair-classification-average-3-datasets">${rowData.pair_classification_average_3_datasets}</div>
                                <div class="reranking-average-4-datasets">${rowData.reranking_average_4_datasets}</div>
                                <div class="retrieval-average-15-datasets">${rowData.retrieval_average_15_datasets}</div>
                                <div class="sts-average-10-datasets">${rowData.sts_average_10_datasets}</div>
                                <div class="summarization-average-1-datasets">${rowData.summarization_average_1_datasets}</div>
                            `;
                            resultsContainer.appendChild(row);
                        });
                        console.log("Data appended to results container.");
                    }
    
                    extractData();
                    scrollTableBody();
    
                } else {
                    console.log("Table body not found, retrying in 500 ms...");
                    setTimeout(checkTableBody, 500); // Retry after 500 ms if tableBody is not found
                }
            })();
            """
        ],
        "url": "https://mteb-leaderboard.hf.space/?__theme=light",
        "baseSelector": "svelte-virtual-table-viewport table",
        "name": "Mteb Leaderboard",
    },
    "ugi": {
        "schema": {
            "name": "leaderboard",
            "baseSelector": ".model-row",
            "fields": [
                {"name": "rank", "selector": ".model-rank", "type": "text"},
                {"name": "name", "selector": ".model-name a", "type": "text"},
                {"name": "url", "selector": ".model-name a", "type": "attribute", "attribute": "href"},
                {"name": "UGI_score", "selector": ".UGI-score", "type": "text"},
                {"name": "W_10_score", "selector": ".W-10-score", "type": "text"},
                {"name": "I_10_score", "selector": ".I-10-score", "type": "text"},
                {"name": "unruly_score", "selector": ".unruly-score", "type": "text"},
                {"name": "internet_score", "selector": ".internet-score", "type": "text"},
                {"name": "stats_score", "selector": ".stats-score", "type": "text"},
                {"name": "writing_score", "selector": ".writing-score", "type": "text"},
                {"name": "polcontro_score", "selector": ".polcontro-score", "type": "text"},
            ],
        },
        "wait_for": """
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
    """,
        "js_code": [
            """
            (function checkTableBody() {
                const tableBody = document.querySelector('svelte-virtual-table-viewport table');
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
                            const modelName = cells[1]?.querySelector('a')?.innerText.trim() || '';
    
                            if (!collectedData.some(data => data.model_name === modelName)) {
                                const rowData = {
                                    rank: cells[0]?.innerText.trim() || '',
                                    model_name: modelName,
                                    model_url: cells[1]?.querySelector('a')?.href || '',
                                    ugi_score: cells[2]?.innerText.trim() || '',
                                    w10_score: cells[3]?.innerText.trim() || '',
                                    i10_score: cells[4]?.innerText.trim() || '',
                                    unruly_score: cells[5]?.innerText.trim() || '',
                                    internet_score: cells[6]?.innerText.trim() || '',
                                    stats_score: cells[7]?.innerText.trim() || '',
                                    writing_score: cells[8]?.innerText.trim() || '',
                                    polcontro_score: cells[9]?.innerText.trim() || ''
                                };
                                collectedData.push(rowData);
                            }
                        });
                    }
    
                    let scrollAttempts = 0;
    
                    function scrollTableBody() {
                        const viewport = tableBody
                        tableBody.scrollTop += 300;
    
                        setTimeout(() => {
                            const newScrollHeight = viewport.scrollHeight;
    
                            if (viewport.scrollTop + viewport.clientHeight >= newScrollHeight || scrollAttempts > 1000) {
                                console.log("Reached the end or max attempts, stopping scroll.");
                                extractData(); // Final extraction in case of remaining items
                                updateResultsContainer(); // Append extracted data to results container
                            } else {
                                console.log("Continuing to scroll...");
                                extractData();
                                scrollAttempts++;
                                scrollTableBody(); // Recursive call to keep scrolling
                            }
                        }, 500);
                    }
    
                    function updateResultsContainer() {
                        resultsContainer.innerHTML = ''; // Clear existing content
                        console.log("total doc", collectedData.length)
                        collectedData.forEach(rowData => {
                            const row = document.createElement('div');
                            row.classList.add('model-row');
                            row.innerHTML = `
                                <div class="model-rank">${rowData.rank}</div>
                                <div class="model-name"><a href="${rowData.model_url}" target="_blank">${rowData.model_name}</a></div>
                                <div class="ugi-score">${rowData.ugi_score}</div>
                                <div class="w10-score">${rowData.w10_score}</div>
                                <div class="i10-score">${rowData.i10_score}</div>
                                <div class="unruly-score">${rowData.unruly_score}</div>
                                <div class="internet-score">${rowData.internet_score}</div>
                                <div class="stats-score">${rowData.stats_score}</div>
                                <div class="writing-score">${rowData.writing_score}</div>
                                <div class="polcontro-score">${rowData.polcontro_score}</div>
                            `;
                            resultsContainer.appendChild(row);
                        });
                        console.log("Data appended to results container.");
                    }
    
                    extractData();
                    scrollTableBody();
    
                } else {
                    console.log("Table body not found, retrying in 500 ms...");
                    setTimeout(checkTableBody, 500); // Retry after 500 ms if tableBody is not found
                }
            })();
            """
        ],
        "url": "https://dontplantoend-ugi-leaderboard.hf.space/?__theme=light",
        "baseSelector": "svelte-virtual-table-viewport table",
        "name": "UGI Leaderboard",
    },
    "vllm": {
        "schema": {
            "name": "leaderboard",
            "baseSelector": ".model-row",
            "fields": [
                {"name": "rank", "selector": ".model-rank", "type": "text"},
                {"name": "name", "selector": ".model-name a", "type": "text"},
                {"name": "url", "selector": ".model-name a", "type": "attribute", "attribute": "href"},
                {"name": "param_b", "selector": ".param-b", "type": "text"},
                {"name": "language_model", "selector": ".language-model", "type": "text"},
                {"name": "vision_model", "selector": ".vision-model", "type": "text"},
                {"name": "avg_score", "selector": ".avg-score", "type": "text"},
                {"name": "avg_rank", "selector": ".avg-rank", "type": "text"},
                {"name": "mmbench_v11", "selector": ".mmbench-v11", "type": "text"},
                {"name": "mmstar", "selector": ".mmstar", "type": "text"},
                {"name": "mmmu_val", "selector": ".mmmu-val", "type": "text"},
                {"name": "mathvista", "selector": ".mathvista", "type": "text"},
                {"name": "ocrbench", "selector": ".ocrbench", "type": "text"},
                {"name": "ai2d", "selector": ".ai2d", "type": "text"},
                {"name": "hallusionbench", "selector": ".hallusionbench", "type": "text"},
                {"name": "mmvet", "selector": ".mmvet", "type": "text"},
            ],
        },
        "wait_for": """
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
    """,
        "js_code": [
            """
            (function checkTableBody() {
                const tableBody = document.querySelector('svelte-virtual-table-viewport table');
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
                            const modelName = cells[1]?.querySelector('a')?.innerText.trim() || '';
    
                            if (!collectedData.some(data => data.model_name === modelName)) {
                                const rowData = {
                                    rank: cells[0]?.innerText.trim() || '',
                                    model_name: modelName,
                                    model_url: cells[1]?.querySelector('a')?.href || '',
                                    param_b: cells[2]?.innerText.trim() || '',
                                    language_model: cells[3]?.innerText.trim() || '',
                                    vision_model: cells[4]?.innerText.trim() || '',
                                    avg_score: cells[5]?.innerText.trim() || '',
                                    avg_rank: cells[6]?.innerText.trim() || '',
                                    mmbench_v11: cells[7]?.innerText.trim() || '',
                                    mmstar: cells[8]?.innerText.trim() || '',
                                    mmmu_val: cells[9]?.innerText.trim() || '',
                                    mathvista: cells[10]?.innerText.trim() || '',
                                    ocrbench: cells[11]?.innerText.trim() || '',
                                    ai2d: cells[12]?.innerText.trim() || '',
                                    hallusionbench: cells[13]?.innerText.trim() || '',
                                    mmvet: cells[14]?.innerText.trim() || ''
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
                                extractData(); // Final extraction in case of remaining items
                                updateResultsContainer(); // Append extracted data to results container
                            } else {
                                console.log("Continuing to scroll...");
                                extractData();
                                scrollAttempts++;
                                scrollTableBody(); // Recursive call to keep scrolling
                            }
                        }, 500);
                    }
    
                    function updateResultsContainer() {
                        resultsContainer.innerHTML = ''; // Clear existing content
                        console.log("Total records:", collectedData.length);
                        collectedData.forEach(rowData => {
                            const row = document.createElement('div');
                            row.classList.add('model-row');
                            row.innerHTML = `
                                <div class="model-rank">${rowData.rank}</div>
                                <div class="model-name"><a href="${rowData.model_url}" target="_blank">${rowData.model_name}</a></div>
                                <div class="param-b">${rowData.param_b}</div>
                                <div class="language-model">${rowData.language_model}</div>
                                <div class="vision-model">${rowData.vision_model}</div>
                                <div class="avg-score">${rowData.avg_score}</div>
                                <div class="avg-rank">${rowData.avg_rank}</div>
                                <div class="mmbench-v11">${rowData.mmbench_v11}</div>
                                <div class="mmstar">${rowData.mmstar}</div>
                                <div class="mmmu-val">${rowData.mmmu_val}</div>
                                <div class="mathvista">${rowData.mathvista}</div>
                                <div class="ocrbench">${rowData.ocrbench}</div>
                                <div class="ai2d">${rowData.ai2d}</div>
                                <div class="hallusionbench">${rowData.hallusionbench}</div>
                                <div class="mmvet">${rowData.mmvet}</div>
                            `;
                            resultsContainer.appendChild(row);
                        });
                        console.log("Data appended to results container.");
                    }
    
                    extractData();
                    scrollTableBody();
    
                } else {
                    console.log("Table body not found, retrying in 500 ms...");
                    setTimeout(checkTableBody, 500); // Retry after 500 ms if tableBody is not found
                }
            })();
            """
        ],
        "url": "https://opencompass-open-vlm-leaderboard.hf.space/?__theme=light",
        "baseSelector": "svelte-virtual-table-viewport table",
        "name": "VLLM Leaderboard",
    },
    "chatbot_arena": {
        "schema": {
            "name": "leaderboard",
            "baseSelector": ".model-row",
            "fields": [
                {"name": "rank_ub", "selector": ".rank-ub", "type": "text"},
                {"name": "rank_style_ctrl", "selector": ".rank-style-ctrl", "type": "text"},
                {"name": "name", "selector": ".model-name a", "type": "text"},
                {"name": "url", "selector": ".model-name a", "type": "attribute", "attribute": "href"},
                {"name": "arena_score", "selector": ".arena-score", "type": "text"},
                {"name": "confidence_interval", "selector": ".confidence-interval", "type": "text"},
                {"name": "votes", "selector": ".votes", "type": "text"},
                {"name": "organization", "selector": ".organization", "type": "text"},
                {"name": "license", "selector": ".license", "type": "text"},
                {"name": "knowledge_cutoff", "selector": ".knowledge-cutoff", "type": "text"},
            ],
        },
        "wait_for": """
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
    """,
        "js_code": [
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
        ],
        "url": "https://lmarena-ai-chatbot-arena-leaderboard.hf.space/",
        "baseSelector": None,
        "name": "Chatbot arena Leaderboard",
    },
}
