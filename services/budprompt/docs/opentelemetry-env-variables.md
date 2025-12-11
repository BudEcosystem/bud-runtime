# OpenTelemetry Environment Variables

| Variable | Description | Default | Valid Values |
|----------|-------------|---------|--------------|
| `OTEL_SDK_DISABLED` | Disable the SDK for all signals | `false` | `true`, `false` |
| `OTEL_SERVICE_NAME` | Service name for resource attribute | `unknown_service` | Any string |
| `OTEL_RESOURCE_ATTRIBUTES` | Resource attributes (comma-separated key=value pairs) | empty | `key1=value1,key2=value2` |
| `OTEL_LOG_LEVEL` | Log level used by SDK internal logger | `info` | `debug`, `info`, `warn`, `error` |
| `OTEL_PROPAGATORS` | Context propagators (comma-separated) | `tracecontext,baggage` | `tracecontext`, `baggage`, `b3`, `b3multi`, `jaeger`, `xray`, `ottrace`, `none` |
| `OTEL_TRACES_SAMPLER` | Sampler for traces | `parentbased_always_on` | `always_on`, `always_off`, `traceidratio`, `parentbased_always_on`, `parentbased_always_off`, `parentbased_traceidratio`, `parentbased_jaeger_remote`, `jaeger_remote` |
| `OTEL_TRACES_SAMPLER_ARG` | Sampler arguments | empty | `0.5` (ratio), or sampler-specific args |
| `OTEL_TRACES_EXPORTER` | Traces exporter | `otlp` | `otlp`, `jaeger`, `zipkin`, `console`, `none` |
| `OTEL_METRICS_EXPORTER` | Metrics exporter | `otlp` | `otlp`, `prometheus`, `console`, `none` |
| `OTEL_LOGS_EXPORTER` | Logs exporter | `otlp` | `otlp`, `console`, `none` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Base OTLP endpoint for all signals | gRPC: `http://localhost:4317`, HTTP: `http://localhost:4318` | URL |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | OTLP endpoint for traces | gRPC: `http://localhost:4317`, HTTP: `http://localhost:4318/v1/traces` | URL |
| `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` | OTLP endpoint for metrics | gRPC: `http://localhost:4317`, HTTP: `http://localhost:4318/v1/metrics` | URL |
| `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` | OTLP endpoint for logs | gRPC: `http://localhost:4317`, HTTP: `http://localhost:4318/v1/logs` | URL |
| `OTEL_EXPORTER_OTLP_PROFILES_ENDPOINT` | OTLP endpoint for profiles | gRPC: `http://localhost:4317`, HTTP: `http://localhost:4318/v1/profiles` | URL |
| `OTEL_EXPORTER_OTLP_HEADERS` | Headers for all OTLP exports | N/A | `key=value,key2=value2` |
| `OTEL_EXPORTER_OTLP_TRACES_HEADERS` | Headers for traces export | N/A | `key=value` |
| `OTEL_EXPORTER_OTLP_METRICS_HEADERS` | Headers for metrics export | N/A | `key=value` |
| `OTEL_EXPORTER_OTLP_LOGS_HEADERS` | Headers for logs export | N/A | `key=value` |
| `OTEL_EXPORTER_OTLP_PROFILES_HEADERS` | Headers for profiles export | N/A | `key=value` |
| `OTEL_EXPORTER_OTLP_TIMEOUT` | Timeout (ms) for all exports | `10000` | Milliseconds |
| `OTEL_EXPORTER_OTLP_TRACES_TIMEOUT` | Timeout (ms) for traces | `10000` | Milliseconds |
| `OTEL_EXPORTER_OTLP_METRICS_TIMEOUT` | Timeout (ms) for metrics | `10000` | Milliseconds |
| `OTEL_EXPORTER_OTLP_LOGS_TIMEOUT` | Timeout (ms) for logs | `10000` | Milliseconds |
| `OTEL_EXPORTER_OTLP_PROFILES_TIMEOUT` | Timeout (ms) for profiles | `10000` | Milliseconds |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | Transport protocol for all signals | SDK-dependent | `grpc`, `http/protobuf`, `http/json` |
| `OTEL_EXPORTER_OTLP_TRACES_PROTOCOL` | Transport protocol for traces | SDK-dependent | `grpc`, `http/protobuf`, `http/json` |
| `OTEL_EXPORTER_OTLP_METRICS_PROTOCOL` | Transport protocol for metrics | SDK-dependent | `grpc`, `http/protobuf`, `http/json` |
| `OTEL_EXPORTER_OTLP_LOGS_PROTOCOL` | Transport protocol for logs | SDK-dependent | `grpc`, `http/protobuf`, `http/json` |
| `OTEL_EXPORTER_OTLP_PROFILES_PROTOCOL` | Transport protocol for profiles | SDK-dependent | `grpc`, `http/protobuf`, `http/json` |
| `OTEL_EXPORTER_ZIPKIN_ENDPOINT` | Zipkin exporter endpoint | `http://localhost:9411/api/v2/spans` | URL |
| `OTEL_EXPORTER_ZIPKIN_TIMEOUT` | Zipkin exporter timeout (ms) | `10000` | Milliseconds |
| `OTEL_EXPORTER_PROMETHEUS_HOST` | Prometheus server hostname | `localhost` | Hostname |
| `OTEL_EXPORTER_PROMETHEUS_PORT` | Prometheus server port | `9464` | Port number |
| `OTEL_BSP_SCHEDULE_DELAY` | Batch Span Processor: delay between exports (ms) | `5000` | Milliseconds |
| `OTEL_BSP_EXPORT_TIMEOUT` | Batch Span Processor: max export time (ms) | `30000` | Milliseconds |
| `OTEL_BSP_MAX_QUEUE_SIZE` | Batch Span Processor: max queue size | `2048` | Integer |
| `OTEL_BSP_MAX_EXPORT_BATCH_SIZE` | Batch Span Processor: max batch size | `512` | Integer |
| `OTEL_BLRP_SCHEDULE_DELAY` | Batch LogRecord Processor: delay between exports (ms) | `1000` | Milliseconds |
| `OTEL_BLRP_EXPORT_TIMEOUT` | Batch LogRecord Processor: max export time (ms) | `30000` | Milliseconds |
| `OTEL_BLRP_MAX_QUEUE_SIZE` | Batch LogRecord Processor: max queue size | `2048` | Integer |
| `OTEL_BLRP_MAX_EXPORT_BATCH_SIZE` | Batch LogRecord Processor: max batch size | `512` | Integer |
| `OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT` | Max attribute value size (all signals) | No limit | Integer |
| `OTEL_ATTRIBUTE_COUNT_LIMIT` | Max attribute count (all signals) | `128` | Integer |
| `OTEL_SPAN_ATTRIBUTE_VALUE_LENGTH_LIMIT` | Max span attribute value size | No limit | Integer |
| `OTEL_SPAN_ATTRIBUTE_COUNT_LIMIT` | Max span attribute count | `128` | Integer |
| `OTEL_SPAN_EVENT_COUNT_LIMIT` | Max span event count | `128` | Integer |
| `OTEL_SPAN_LINK_COUNT_LIMIT` | Max span link count | `128` | Integer |
| `OTEL_EVENT_ATTRIBUTE_COUNT_LIMIT` | Max attributes per span event | `128` | Integer |
| `OTEL_LINK_ATTRIBUTE_COUNT_LIMIT` | Max attributes per span link | `128` | Integer |
| `OTEL_LOGRECORD_ATTRIBUTE_VALUE_LENGTH_LIMIT` | Max log record attribute value size | No limit | Integer |
| `OTEL_LOGRECORD_ATTRIBUTE_COUNT_LIMIT` | Max log record attribute count | `128` | Integer |
| `OTEL_METRICS_EXEMPLAR_FILTER` | Filter for measurements that can become Exemplars | `trace_based` | `trace_based`, `always_on`, `always_off` |
| `OTEL_METRIC_EXPORT_INTERVAL` | Metrics export interval (ms) | `60000` | Milliseconds |
| `OTEL_METRIC_EXPORT_TIMEOUT` | Metrics export timeout (ms) | `30000` | Milliseconds |
| `OTEL_EXPERIMENTAL_CONFIG_FILE` | Path to declarative YAML config file | N/A | File path |
