# BudAdmin Observability Dashboard Documentation

## Overview

The BudAdmin Observability Dashboard provides comprehensive visualization and analysis of API gateway traffic, model inference requests, and system performance metrics. It offers real-time insights into API usage patterns, geographic distribution, performance bottlenecks, and security events.

## Features

### 1. Metrics Dashboard

The main metrics view provides aggregated analytics across multiple dimensions:

- **Key Performance Indicators (KPIs)**
  - Total requests and success rate
  - Average, P95, and P99 latency
  - Token usage (input/output breakdown)
  - Error rates and failure analysis

- **Time Series Visualizations**
  - Request volume over time
  - Latency trends (avg, P95, P99)
  - Token usage patterns
  - Requests per second (RPS)

- **Distribution Charts**
  - Hourly request distribution
  - Latency distribution buckets
  - Geographic heat map
  - Top models, projects, and deployments

### 2. Request Listing

Detailed table view of individual inference requests:

- **Request Details**
  - Timestamp with timezone support
  - Project and deployment information
  - Prompt preview with full view on click
  - Response time and status

- **Filtering Capabilities**
  - Date range selection
  - Token count ranges
  - Latency thresholds
  - Success/failure status

- **Export Options**
  - CSV export for spreadsheet analysis
  - JSON export for programmatic processing

### 3. Request Detail Modal

Comprehensive view of individual requests:

- **Overview Tab**
  - Complete request/response details
  - Token usage breakdown
  - Performance metrics (TTFT, latency)
  - Cost analysis

- **Messages Tab**
  - Full conversation history
  - System, user, and assistant messages
  - Token counts per message

- **Performance Tab**
  - Detailed timing metrics
  - Token generation speed
  - Streaming performance (if applicable)

- **Raw Data Tab**
  - Complete JSON request/response
  - Headers and metadata
  - Error details (if failed)

- **Feedback Tab**
  - User ratings and feedback
  - Boolean metrics (helpful, accurate, etc.)
  - Comments and annotations

## Component Architecture

### Directory Structure

```
budadmin/src/
├── pages/home/observability/
│   ├── index.tsx              # Main observability page
│   └── MetricsTab.tsx         # Metrics dashboard component
├── components/
│   ├── charts/
│   │   ├── MultiSeriesLineChart.tsx  # Multi-line time series
│   │   ├── GroupedBarChart.tsx       # Grouped bar charts
│   │   └── GeoMapChart.tsx          # Geographic heat map
│   ├── inferences/
│   │   ├── InferenceListView.tsx    # Request listing table
│   │   ├── InferenceDetailModal.tsx # Request detail view
│   │   ├── InferenceFilters.tsx     # Advanced filtering
│   │   ├── ClientInfo.tsx           # Client metadata display
│   │   ├── GeographicInfo.tsx       # Geographic details
│   │   └── RequestMetadata.tsx      # Request metadata
│   └── ui/bud/table/
│       └── InferenceListTable.tsx   # Reusable table component
└── stores/
    └── useInferences.ts              # Zustand state management
```

### Key Components

#### 1. MetricsTab Component

```typescript
interface MetricsTabProps {
  timeRange: [dayjs.Dayjs, dayjs.Dayjs];
  inferences: InferenceListItem[];
  isLoading: boolean;
  viewBy: 'model' | 'deployment' | 'project' | 'user';
  isActive?: boolean;  // For chart resize handling
}

const MetricsTab: React.FC<MetricsTabProps> = ({
  timeRange,
  inferences,
  isLoading,
  viewBy,
  isActive
}) => {
  // Calculate aggregated metrics
  // Render charts with consistent color mapping
  // Handle dynamic grouping based on viewBy
}
```

#### 2. Inference Store

```typescript
interface InferenceStore {
  inferences: InferenceListItem[];
  pagination: PaginationState;
  filters: FilterState;
  isLoading: boolean;

  // Actions
  fetchInferences: (projectId?: string) => Promise<void>;
  fetchInferenceDetail: (inferenceId: string) => Promise<InferenceDetail>;
  exportInferences: (format: 'csv' | 'json') => Promise<void>;
  setFilters: (filters: Partial<FilterState>) => void;
  setPagination: (pagination: Partial<PaginationState>) => void;
}
```

#### 3. Chart Components

All charts use ECharts for consistent styling and performance:

```typescript
// Multi-series line chart for time series data
<MultiSeriesLineChart
  data={{
    categories: ['00:00', '01:00', ...],  // X-axis labels
    series: [
      {
        name: 'Model A',
        data: [100, 120, ...],
        color: '#965CDE'  // Consistent color
      }
    ]
  }}
/>

// Grouped bar chart for comparisons
<GroupedBarChart
  data={{
    categories: ['0-100ms', '100-500ms', ...],
    series: [...]
  }}
/>

// Geographic heat map
<GeoMapChart
  data={geographicData}
  onCountryClick={(country) => {...}}
/>
```

## UI/UX Features

### 1. View By Selection

Dynamic grouping of metrics by different dimensions:

- **Model**: Group by AI model
- **Deployment**: Group by deployment/endpoint
- **Project**: Group by project
- **User**: Group by user/client

### 2. Time Range Selection

Flexible time range options:

- Quick presets (1 hour, 6 hours, 24 hours, 7 days, 30 days)
- Custom date/time range picker
- Automatic data refresh

### 3. Color Consistency

Consistent color mapping across all charts:

```typescript
const colorPalette = [
  '#965CDE',  // Primary purple (theme color)
  '#3F8EF7',  // Blue
  '#FFC442',  // Yellow
  '#52C41A',  // Green
  '#FF6B6B',  // Red
  // ... more colors
];

// Entity gets same color across all charts
const getEntityColor = (entityName: string) => {
  // Memoized color assignment
  return assignedColor;
};
```

### 4. Responsive Design

- Charts automatically resize when switching tabs
- Mobile-responsive layout
- Adaptive chart legends (bottom position)

## State Management

### Zustand Store Structure

```typescript
const useInferences = create<InferenceStore>((set, get) => ({
  // State
  inferences: [],
  pagination: { page: 1, pageSize: 20, total: 0 },
  filters: {},
  isLoading: false,

  // Actions
  fetchInferences: async (projectId?: string) => {
    set({ isLoading: true });
    try {
      const response = await api.getInferences({
        projectId,
        ...get().filters,
        ...get().pagination
      });
      set({
        inferences: response.data,
        pagination: { ...get().pagination, total: response.total }
      });
    } finally {
      set({ isLoading: false });
    }
  }
}));
```

## API Integration

### Endpoints Used

1. **List Inferences**
   ```typescript
   POST /api/v1/metrics/inferences/list
   {
     project_id?: string;
     page: number;
     page_size: number;
     filters: {
       from_date?: string;
       to_date?: string;
       min_tokens?: number;
       max_tokens?: number;
       min_latency?: number;
       max_latency?: number;
     };
   }
   ```

2. **Get Inference Detail**
   ```typescript
   GET /api/v1/metrics/inferences/{inference_id}
   ```

3. **Get Feedback**
   ```typescript
   GET /api/v1/metrics/inferences/{inference_id}/feedback
   ```

4. **Export Data**
   ```typescript
   POST /api/v1/metrics/inferences/export
   {
     format: 'csv' | 'json';
     filters: {...};
   }
   ```

## Styling and Theming

### Color Scheme

```scss
// Dark theme colors
$background-primary: #0A0A0A;
$background-secondary: #101010;
$border-color: #1F1F1F;
$text-primary: #EEEEEE;
$text-secondary: #B3B3B3;
$accent-purple: #965CDE;
$accent-purple-bg: #1E0C34;

// Chart colors
$chart-blue: #3F8EF7;
$chart-yellow: #FFC442;
$chart-green: #52C41A;
$chart-red: #FF6B6B;
```

### Component Styling

```scss
// Segmented control (View By selector)
.antSegmented {
  background-color: #1a1a1a !important;
  border: 1px solid #333333 !important;

  .ant-segmented-item-selected {
    background-color: #1E0C34 !important;
    border-color: #965CDE !important;
  }
}

// Chart cards
.chart-card {
  background: #101010;
  border: 1px solid #1F1F1F;
  border-radius: 6px;
  padding: 1.5rem;
}
```

## Performance Optimizations

### 1. Data Aggregation

- Server-side aggregation in ClickHouse
- Client-side memoization for expensive calculations
- Virtualized table rendering for large datasets

### 2. Chart Rendering

- Lazy loading of chart libraries
- Debounced resize handlers
- Canvas-based rendering for performance

### 3. State Management

- Selective re-rendering with Zustand
- Optimistic updates for UI responsiveness
- Background data fetching

## Usage Guide

### Viewing Metrics

1. **Select Time Range**: Use quick presets or custom picker
2. **Choose View By**: Select grouping dimension
3. **Analyze Charts**: Hover for details, click for drill-down
4. **Export Data**: Download CSV/JSON for external analysis

### Analyzing Requests

1. **Browse Requests**: View table with sorting and pagination
2. **Filter Results**: Apply date, token, or latency filters
3. **View Details**: Click request for comprehensive modal
4. **Export Results**: Download filtered data

### Identifying Issues

1. **Performance Bottlenecks**
   - Check P95/P99 latency charts
   - Analyze latency distribution
   - Identify slow endpoints

2. **Error Patterns**
   - Monitor error rate trends
   - Check failure distribution
   - Review error messages

3. **Usage Anomalies**
   - Detect traffic spikes
   - Identify unusual geographic patterns
   - Monitor token usage trends

## Troubleshooting

### Common Issues

1. **Charts Not Displaying**
   - Verify data is available for selected time range
   - Check browser console for errors
   - Ensure ECharts library loaded

2. **Data Not Loading**
   - Verify authentication token
   - Check network requests
   - Review API response errors

3. **Chart Resize Issues**
   - Charts auto-resize on tab switch
   - Manual refresh available
   - Check container dimensions

4. **Export Failures**
   - Verify export permissions
   - Check data size limits
   - Review browser download settings

## Future Enhancements

- [ ] Real-time data streaming
- [ ] Custom metric definitions
- [ ] Alerting and notifications
- [ ] Comparative analysis tools
- [ ] Machine learning insights
- [ ] Advanced anomaly detection
- [ ] Custom dashboard layouts
- [ ] Collaborative annotations

## Development

### Running Locally

```bash
cd services/budadmin
npm install
npm run dev
# Opens at http://localhost:8007
```

### Testing

```bash
# Unit tests
npm run test

# E2E tests
npm run test:e2e

# Component testing
npm run test:components
```

### Building

```bash
# Production build
npm run build

# Analyze bundle
npm run analyze
```

## Configuration

### Environment Variables

```bash
# API Configuration
NEXT_PUBLIC_BASE_URL=http://localhost:8001
NEXT_PUBLIC_API_VERSION=v1

# Feature Flags
NEXT_PUBLIC_ENABLE_EXPORT=true
NEXT_PUBLIC_ENABLE_FEEDBACK=true

# Chart Configuration
NEXT_PUBLIC_MAX_CHART_POINTS=1000
NEXT_PUBLIC_DEFAULT_TIME_RANGE=7d
```

### Chart Configuration

```typescript
// Chart default options
const defaultChartOptions = {
  animation: true,
  responsive: true,
  maintainAspectRatio: false,
  legend: {
    position: 'bottom',
    textStyle: {
      color: '#B3B3B3'
    }
  },
  tooltip: {
    trigger: 'axis',
    backgroundColor: '#1a1a1a',
    borderColor: '#333'
  }
};
```
