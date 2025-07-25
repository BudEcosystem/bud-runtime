# Performance Analysis: Observability Analytics Endpoint


## 1. Executive Summary (TL;DR)

This report analyzes the performance of the `/observability/analytics` endpoint under a heavy load scenario. Our findings show that while network latency from large payloads was the initial bottleneck, server-side JSON serialization was also a significant factor.

- **Initial State:** The endpoint was slow, with an **8.5-second** end-to-end latency, dominated by the time required to download a **15.59 MB** JSON response.
- **Compression Solution:** Implementing the `starlette-compress` middleware dramatically reduced the payload to **143 KB** and cut latency to **4.75 seconds**.
- **Serialization Solution:** By also switching to `ORJSONResponse`, we further optimized server-side processing, achieving a final end-to-end latency of **3.95 seconds**.

**Recommendation:** The combination of `starlette-compress` and `ORJSONResponse` is the clear winner. This configuration should be adopted immediately. Future optimizations should focus on the remaining server-side processing tasks and client-side data handling strategies.

## 2. Test Scenario

The analysis was conducted using a high-load request payload designed to test the system's limits.

**Request Payload:**
```json
{
  "metrics": ["concurrent_requests"],
  "from_date": "2024-05-09T07:39:27.625Z",
  "to_date": "2025-06-09T07:39:27.625Z",
  "frequency_unit": "day",
  "filters": {},
  "group_by": ["model", "project", "endpoint"],
  "return_delta": true,
  "fill_time_gaps": true
}
```

**Key Characteristics of the Test:**
* **Database Scale:** The query runs against a ClickHouse database with over **1 million rows**.
* **Time Range:** A full year of data.
* **Cardinality:** The query groups data by three dimensions (`model`, `project`, `endpoint`) with no filters, resulting in a very large and detailed time-series result set.
* **Complexity:** The request requires calculating deltas and filling time gaps, adding to the processing load.

## 3. Performance Observations

Four distinct tests were performed to measure the impact of response compression and JSON serialization on end-to-end (E2E) latency.

| Middleware / Response Class | Response Size | Server Time | Download Time | Total E2E Latency | Result |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **None (Baseline)** | 15.59 MB | 2.79 s | 5.76 s | 8.50 s | 🐌 **Poor** |
| FastAPI `GZipMiddleware` | 3.39 MB | 3.48 s | 7.51 s | 10.99 s | ❌ **Worse** |
| `starlette-compress` | 143 KB | 3.72 s | 1.03 s | 4.75 s | ✅ **Excellent** |
| **`starlette-compress` + `ORJSONResponse`** | **143 KB** | **3.01 s** | **0.94 s** | **3.95 s** | 🚀 **Optimal** |

### 3.1. Analysis of Results

* **Baseline (No Compression):** The primary bottleneck was clearly the **5.76s download time** for the 15.59 MB payload.

* **FastAPI `GZipMiddleware`:** This middleware negatively impacted performance, demonstrating that not all compression is beneficial. The overhead of its Gzip implementation outweighed the gains from a moderate size reduction.

* **`starlette-compress`:** This was a game-changer for network transfer. It achieved a **~99% reduction** in payload size (likely using Brotli), which slashed download time to just **1.03 seconds** and more than halved the total E2E latency.

* **`starlette-compress` + `ORJSONResponse`:** This combination yielded the best performance. While response size was unchanged, using the high-performance `orjson` library **reduced server time by an additional ~700ms**. This proves that a significant portion of the server's workload was being spent on serializing the large dataset into JSON, a bottleneck that `orjson` effectively resolves.

## 4. Server-Side Performance Deep Dive

The internal performance logs provide further insight into the server's behavior.

> **Performance Log Snippet:**
>
> ```json
> "metrics_summary": {
>   "query_execution": {"avg_ms": 752.45},
>   "query_building": {"avg_ms": 0.13},
>   "result_processing": {"avg_ms": 1091.18},
>   "cache": {"hit_rate": 0.0}
> }
> ```

**Breakdown:**
* **Query Building (`~0.1ms`):** Negligible.
* **Query Execution (`~752ms`):** Excellent. ClickHouse is not the bottleneck.
* **Result Processing (`~1.1s`):** This was identified as a key area for optimization. The final test confirmed this hypothesis: by switching to `orjson`, we reduced the overall server time by **~700ms**, indicating that JSON serialization was responsible for the majority of this processing time. The remaining ~400ms is likely due to Pydantic model validation and other data transformations.
* **Total vs. Measured:** The sum of internal tasks (`query_execution` + `result_processing`) is `752ms + 1091ms ≈ 1.84s`. The final measured server time was **3.01s**. The remaining **~1.17s** can be attributed to the FastAPI/Starlette request-response cycle and the CPU time spent on Brotli compression.

## 5. Conclusions & Future Optimizations

### Immediate Actions

1.  **Adopt `starlette-compress`:** This is essential for minimizing network latency.
2.  **Set `ORJSONResponse` as the Default:** Given the significant reduction in server time, `ORJSONResponse` should be used as the default response class for all data-heavy API endpoints.

### Future Optimizations

While the endpoint is now significantly faster, the following strategies can ensure long-term scalability.

1.  **Client-Side Pagination Strategy:** Returning a potentially massive payload, even compressed, is not ideal. While adding server-side cursor-based pagination introduces significant complexity to the query generation, a pragmatic approach is to enforce a **client-side pagination strategy**. The client should be responsible for making multiple, smaller requests with narrower `from_date` and `to_date` ranges (e.g., fetching data month by month) to avoid requesting a full year of granular data at once.

2.  **Further Optimize Result Processing:** The successful optimization using `orjson` was a major win. The remaining ~400ms in this step can be investigated by profiling Pydantic model validation and any other Python-based data transformations.

3.  **Implement Caching:** The cache hit rate was 0%. For frequently requested, identical queries, implementing a caching layer (e.g., Redis) could serve results in milliseconds, providing the best possible experience for common dashboards or reports.