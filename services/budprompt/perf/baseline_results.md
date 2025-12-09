# BudPrompt Performance Baseline Test Results

**Date:** 2025-12-09
**Environment:** Local development (Kubernetes pod)
**Endpoint:** `POST http://localhost:9088/v1/responses`
**Timeout:** 10s per request
**Duration:** 10s per test

## Test Configuration

```bash
echo 'POST http://localhost:9088/v1/responses' | vegeta attack \
    -header="Content-Type: application/json" \
    -header="Authorization: Bearer <token>" \
    -body=./perf/body.json \
    -duration=10s \
    -rate=<RATE> \
    -timeout=10s \
    -redirects=3 \
| vegeta report
```

## Results Summary

| Rate | Total Requests | Success % | Timeouts | Mean Latency | p50 Latency | p99 Latency |
|------|----------------|-----------|----------|--------------|-------------|-------------|
| 5 req/s | 50 | **90%** | 5 | 1,497ms | 443ms | 10s |
| 10 req/s | 100 | **95%** | 5 | 847ms | 296ms | 10s |
| 15 req/s | 150 | **92%** | 12 | 1,096ms | 291ms | 10s |
| 20 req/s | 200 | **91.5%** | 17 | 1,137ms | 288ms | 10s |
| 30 req/s | 300 | **94%** | 17 | 866ms | 286ms | 10s |
| 50 req/s | 500 | **85.6%** | 70 | 2,408ms | 1,141ms | 10s |
| 75 req/s | 750 | **69.2%** | 228 | 4,955ms | 3,387ms | 10s |
| 100 req/s | 1000 | **37.8%** | 622 | 9,065ms | 10s | 10s |

## Key Observations

1. **Baseline p50 latency is ~290ms** - this is the actual processing time per request
2. **Even at 5 req/s, there are timeouts** - something is occasionally blocking
3. **Cliff begins around 50 req/s** - success drops from 94% to 85%
4. **Severe degradation at 75+ req/s** - latency explodes, timeouts dominate
5. **At 100 req/s, 62% failure rate** - system is completely overwhelmed

## Throughput Analysis

- **Stable throughput:** ~25-30 successful req/s (observed across all tests)
- **Maximum sustainable rate:** ~30-40 req/s with >90% success
- **Breaking point:** 50 req/s (success drops below 90%)

## Raw Test Output

### 5 req/s
```
Requests      [total, rate, throughput]         50, 5.10, 3.69
Duration      [total, attack, wait]             12.201s, 9.8s, 2.401s
Latencies     [min, mean, 50, 90, 95, 99, max]  277.595ms, 1.497s, 443.459ms, 5.938s, 10.002s, 10.009s, 10.009s
Bytes In      [total, mean]                     59130, 1182.60
Bytes Out     [total, mean]                     8010, 160.20
Success       [ratio]                           90.00%
Status Codes  [code:count]                      0:5  200:45
```

### 10 req/s
```
Requests      [total, rate, throughput]         100, 10.10, 8.41
Duration      [total, attack, wait]             11.301s, 9.899s, 1.402s
Latencies     [min, mean, 50, 90, 95, 99, max]  268.726ms, 847.245ms, 296.322ms, 1.017s, 5.586s, 10.002s, 10.003s
Bytes In      [total, mean]                     124830, 1248.30
Bytes Out     [total, mean]                     16910, 169.10
Success       [ratio]                           95.00%
Status Codes  [code:count]                      0:5  200:95
```

### 15 req/s
```
Requests      [total, rate, throughput]         150, 15.10, 12.25
Duration      [total, attack, wait]             11.268s, 9.933s, 1.335s
Latencies     [min, mean, 50, 90, 95, 99, max]  265.64ms, 1.096s, 290.666ms, 829.599ms, 10.001s, 10.003s, 10.008s
Bytes In      [total, mean]                     181332, 1208.88
Bytes Out     [total, mean]                     24564, 163.76
Success       [ratio]                           92.00%
Status Codes  [code:count]                      0:12  200:138
```

### 20 req/s
```
Requests      [total, rate, throughput]         200, 20.10, 15.98
Duration      [total, attack, wait]             11.45s, 9.95s, 1.501s
Latencies     [min, mean, 50, 90, 95, 99, max]  263.687ms, 1.137s, 288.02ms, 820.266ms, 10.001s, 10.002s, 10.008s
Bytes In      [total, mean]                     240462, 1202.31
Bytes Out     [total, mean]                     32574, 162.87
Success       [ratio]                           91.50%
Status Codes  [code:count]                      0:17  200:183
```

### 30 req/s
```
Requests      [total, rate, throughput]         300, 30.10, 24.45
Duration      [total, attack, wait]             11.535s, 9.967s, 1.568s
Latencies     [min, mean, 50, 90, 95, 99, max]  8.557ms, 866.218ms, 286.338ms, 853.179ms, 10.001s, 10.001s, 10.003s
Bytes In      [total, mean]                     370692, 1235.64
Bytes Out     [total, mean]                     50374, 167.91
Success       [ratio]                           94.00%
Status Codes  [code:count]                      0:17  200:282  500:1
```

### 50 req/s
```
Requests      [total, rate, throughput]         500, 50.10, 25.29
Duration      [total, attack, wait]             16.921s, 9.98s, 6.942s
Latencies     [min, mean, 50, 90, 95, 99, max]  7.021ms, 2.408s, 1.141s, 10.001s, 10.001s, 10.002s, 10.007s
Bytes In      [total, mean]                     562680, 1125.36
Bytes Out     [total, mean]                     76540, 153.08
Success       [ratio]                           85.60%
Status Codes  [code:count]                      0:70  200:428  500:2
```

### 75 req/s
```
Requests      [total, rate, throughput]         750, 75.11, 26.00
Duration      [total, attack, wait]             19.96s, 9.985s, 9.975s
Latencies     [min, mean, 50, 90, 95, 99, max]  6.293ms, 4.955s, 3.387s, 10.001s, 10.001s, 10.002s, 10.005s
Bytes In      [total, mean]                     682398, 909.86
Bytes Out     [total, mean]                     92916, 123.89
Success       [ratio]                           69.20%
Status Codes  [code:count]                      0:228  200:519  500:3
```

### 100 req/s
```
Requests      [total, rate, throughput]         1000, 100.11, 18.91
Duration      [total, attack, wait]             19.99s, 9.989s, 10.001s
Latencies     [min, mean, 50, 90, 95, 99, max]  4.182s, 9.065s, 10s, 10.001s, 10.001s, 10.003s, 10.019s
Bytes In      [total, mean]                     496692, 496.69
Bytes Out     [total, mean]                     67284, 67.28
Success       [ratio]                           37.80%
Status Codes  [code:count]                      0:622  200:378
```

## Identified Bottlenecks (To Investigate)

1. **Threading lock in singleton pattern** - `budprompt/shared/singleton.py` uses `threading.Lock` which blocks async event loop
2. **Per-request service instantiation** - `ResponsesService()` and `PromptExecutorService()` created per request
3. **Redis connection pool not configured** - Default pool settings may be limiting
4. **Single uvicorn worker** - Only 1 worker process handling all requests

## Next Steps

- [ ] Implement module-level singleton initialization (remove threading lock)
- [ ] Configure Redis connection pool with explicit limits
- [ ] Use shared service instances instead of per-request creation
- [ ] Re-run benchmarks after each optimization
