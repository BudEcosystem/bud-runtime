import { tempApiBaseUrl } from "@/components/environment";
import { AppRequest } from "src/pages/api/requests";
import { create } from "zustand";
import { Provider } from "./useCloudProviders";
import { Model } from "./useModels";
import { Cluster } from "./useCluster";

type GetbenchmarkParams = {
  page: number;
  limit: number;
  order_by?: string;
  name?: string;
  email?: string;
  role?: string;
  status?: string;
};
export type Benchmark = {
  key?: string;
  created_at?: string;
  model: [];
  cluster: [];
  name?: string;
  modelName?: string;
  modelImage?: string;
  clusterName?: string;
  clusterImage?: string;
  node_type?: any;
  vendor_type?: string;
  status?: string;
  concurrentRequest?: string;
  concurrency?: number;
  max_input_tokens?: number;
  max_output_tokens?: number;
  nodes?: any[];
  description?: string;
  tags?: any[];
  tpot?: string;
  ttft?: string;
  id?: string;
  eval_with?: string;
  dataset_ids?: [];
};

export type ModelClusterDetails = {
  cluster?: Cluster;
  deployment_config?: any;
  id: string;
  model: Model;
  name?: string;
  status?: string;
  // Benchmark metadata
  concurrency?: number;
  max_input_tokens?: number;
  max_output_tokens?: number;
  eval_with?: string;
  description?: string;
  tags?: any[];
  nodes?: any[];
  dataset_ids?: string[];
  dataset_names?: string[];
  reason?: string;
  created_at?: string;
  modified_at?: string;
};
export type BenchmarkResult = {
  output_throughput: number;
  median_ttft_ms: number;
  median_tpot_ms: number;
  median_itl_ms: number;
  median_e2el_ms: number;
  p25_ttft_ms: number;
  p25_output_throughput_per_user: number;
  p25_tpot_ms: number;
  p25_itl_ms: number;
  p25_e2el_ms: number;
  modified_at: string;
  p75_output_throughput_per_user: number;
  p75_ttft_ms: number;
  p75_tpot_ms: number;
  p75_itl_ms: number;
  p75_e2el_ms: number;
  successful_requests: number;
  p95_output_throughput_per_user: number;
  p95_ttft_ms: number;
  p95_tpot_ms: number;
  p95_itl_ms: number;
  p95_e2el_ms: number;
  duration: number;
  total_input_tokens: number;
  p99_output_throughput_per_user: number;
  p99_ttft_ms: number;
  p99_tpot_ms: number;
  p99_itl_ms: number;
  p99_e2el_ms: number;
  id: string;
  total_output_tokens: number;
  min_output_throughput_per_user: number;
  min_ttft_ms: number;
  min_tpot_ms: number;
  min_itl_ms: number;
  min_e2el_ms: number;
  request_throughput: number;
  max_output_throughput_per_user: number;
  max_ttft_ms: number;
  max_tpot_ms: number;
  max_itl_ms: number;
  max_e2el_ms: number;
  benchmark_id: string;
  input_throughput: number;
  mean_ttft_ms: number;
  mean_tpot_ms: number;
  mean_itl_ms: number;
  mean_e2el_ms: number;
  mean_output_throughput_per_user: number;
  created_at: string;
};
export type BenchmarkAnalysisInput = {
  field1?: string;
  field2?: string;
};
export type RequestMetricsParams = {
  benchmark_id?: string;
  page?: any;
  limit?: any;
};
export type Field1VsFieldParams = {
  benchmark_id?: string;
  field1?: any;
  field2?: any;
};

export type FilterParams = {
  page?: number;
  limit?: number;
  search?: boolean;
  model_name?: string;
  cluster_name?: string;
  resource?: string;
};

export type DistributionParams = {
  benchmark_id?: string;
  num_bins?: any;
};
export type RequestMetricsData = {
  benchmark_id?: string;
  dataset_id?: string;
  itl: number[];
  itl_sum: number;
  latency: number;
  output_len: number;
  prompt_len: number;
  req_output_throughput: number;
  success: boolean;
  error: string | null;
  tpot: number;
  ttft: number;
};

// create zustand store
export const useBenchmarks = create<{
  modelFilterList: any;
  clusterFilterList: any;
  totalPages: number;
  totalUsers: number;
  filters: any;
  loading: boolean;
  benchmarks: Benchmark[];
  modelClusterDetails: ModelClusterDetails | null;
  selectedBenchmark: Benchmark | null;
  benchmarkResult: BenchmarkResult | null;
  benchmarkRequestMetrics: RequestMetricsData[] | null;
  benchmarkRequestMetricsTotalCount: any | null;
  benchmarkMetricsData: any | null;
  benchmarkAnalysisTtftVsTokenData: any | null;
  inputDistribution: any | null;
  outputDistribution: any | null;
  inputSizeVsTTFT: any | null;
  outputSizeVsTPOT: any | null;
  outputSizeVsLatency: any | null;

  getBenchmarks: (parms: any) => void;
  fetchBenchmarks: (params: GetbenchmarkParams) => Promise<Benchmark[]>;
  getBenchmarkModelClusterDetails: (id: string) => Promise<any>;
  getBenchmarkResult: (id: string) => Promise<any>;
  setSelectedBenchmark: (benchmark: Benchmark) => void;
  getBenchmarkAnalysisField1VsField2: (
    params: Field1VsFieldParams,
  ) => Promise<any>;
  getBenchmarkResultRequestMetrics: (params: RequestMetricsParams) => void;
  getTTFTvsTokens: (benchmarkId: string) => void;
  getInputSizeVsTTFT: (benchmarkId: string) => void;
  getOutputSizeVsTPOT: (benchmarkId: string) => void;
  getOutputSizeVsLatency: (benchmarkId: string) => void;
  getInputDistribution: (params: DistributionParams) => void;
  getOutputDistribution: (params: DistributionParams) => void;
  getfilterList: (params: FilterParams) => Promise<any>;
}>((set, get) => ({
  modelFilterList: undefined,
  clusterFilterList: undefined,
  filters: {},
  totalPages: 0,
  totalUsers: 0,
  loading: true,
  benchmarks: [],
  modelClusterDetails: null,
  selectedBenchmark: null,
  benchmarkResult: null,
  benchmarkRequestMetrics: null,
  benchmarkRequestMetricsTotalCount: null,
  benchmarkMetricsData: null,
  benchmarkAnalysisTtftVsTokenData: null,
  inputDistribution: null,
  outputDistribution: null,
  inputSizeVsTTFT: null,
  outputSizeVsTPOT: null,
  outputSizeVsLatency: null,

  setSelectedBenchmark: (benchmark: Benchmark) => {
    set({ selectedBenchmark: benchmark });
  },

  fetchBenchmarks: async (params: GetbenchmarkParams) => {
    Object.keys(params).forEach((key) => {
      if (!params[key]) {
        delete params[key];
      }
    });

    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(
        `${tempApiBaseUrl}/benchmark`,
        {
          params: {
            ...params,
          },
        },
      );
      set({
        totalPages: response.data.total_pages,
        totalUsers: response.data.total_record,
      });
      const listData = response.data;
      const updatedListData = listData.benchmarks;
      return updatedListData;
    } catch (error) {
      console.error("Error creating model:", error);
    } finally {
      set({ loading: false });
    }
  },

  getBenchmarks: async (params: any) => {
    let updatedListData = await get().fetchBenchmarks(params);
    if (params.page !== 1) {
      updatedListData = [...get().benchmarks, ...updatedListData];
    }
    set({ benchmarks: updatedListData, filters: params });
  },

  getBenchmarkModelClusterDetails: async (id: string) => {
    if (!id) {
      return;
    }
    const response: any = await AppRequest.Get(
      `${tempApiBaseUrl}/benchmark/${id}/model-cluster-detail`,
    );
    set({ modelClusterDetails: response?.data?.result });
  },
  getBenchmarkResult: async (id: string) => {
    if (!id) {
      return;
    }
    const response: any = await AppRequest.Get(
      `${tempApiBaseUrl}/benchmark/result?benchmark_id=${id}`,
    );
    set({ benchmarkResult: response?.data?.param?.result });
  },

  getBenchmarkResultRequestMetrics: async (params: RequestMetricsParams) => {
    if (!params) {
      return;
    }
    const response: any = await AppRequest.Get(
      `${tempApiBaseUrl}/benchmark/request-metrics`,
      {
        params: {
          benchmark_id: params.benchmark_id,
          page: params.page,
          limit: params.limit,
        },
      },
    );
    set({ benchmarkRequestMetrics: response?.data?.items });
    set({ benchmarkRequestMetricsTotalCount: response?.data?.total_items });
  },

  getInputDistribution: async (params: DistributionParams) => {
    const response: any = await AppRequest.Post(
      `${tempApiBaseUrl}/benchmark/dataset/input-distribution?benchmark_id=${
        params.benchmark_id
      }&num_bins=${params.num_bins || 5}`,
      get().selectedBenchmark?.dataset_ids,
    );
    set({ inputDistribution: response?.data?.param?.result });
    // console.log("inputDistribution", response);
  },

  getOutputDistribution: async (params: DistributionParams) => {
    const response: any = await AppRequest.Post(
      `${tempApiBaseUrl}/benchmark/dataset/output-distribution?benchmark_id=${
        params.benchmark_id
      }&num_bins=${params.num_bins || 5}`,
      get().selectedBenchmark?.dataset_ids,
    );
    set({ outputDistribution: response?.data?.param?.result });
    // console.log("OutputDistribution", response);
  },

  getBenchmarkAnalysisField1VsField2: async (params: Field1VsFieldParams) => {
    const response: any = await AppRequest.Post(
      `${tempApiBaseUrl}/benchmark/${params.benchmark_id}/analysis/field1_vs_field2?field1=${params.field1}&field2=${params.field2}`,
    );
    return response?.data?.param?.result;
  },

  // TTFT vs Tokens Input scatter chart =============================
  getTTFTvsTokens: async (benchmarkId: string) => {
    get()
      .getBenchmarkAnalysisField1VsField2({
        benchmark_id: benchmarkId as string,
        field1: "ttft",
        field2: "tpot",
      })
      .then((result) => {
        if (result) {
          set({ benchmarkAnalysisTtftVsTokenData: result });
        }
      })
      .catch((error) => {
        console.error("Error fetching TTFT vs Tokens:", error);
      });
  },
  // TTFT vs Tokens Input scatter chart ============================= /

  // InputSizeVsTTFT line chart =============================
  getInputSizeVsTTFT: async (benchmarkId: string) => {
    get()
      .getBenchmarkAnalysisField1VsField2({
        benchmark_id: benchmarkId as string,
        field1: "prompt_len",
        field2: "ttft",
      })
      .then((result) => {
        if (result) {
          set({ inputSizeVsTTFT: result });
        }
      })
      .catch((error) => {
        console.error("Error fetching TTFT vs Tokens:", error);
      });
  },
  // InputSizeVsTTFT line chart ============================= /

  // OutputSizeVsTPOT line chart =============================
  getOutputSizeVsTPOT: async (benchmarkId: string) => {
    get()
      .getBenchmarkAnalysisField1VsField2({
        benchmark_id: benchmarkId as string,
        field1: "output_len",
        field2: "tpot",
      })
      .then((result) => {
        if (result) {
          set({ outputSizeVsTPOT: result });
        }
      })
      .catch((error) => {
        console.error("Error fetching TTFT vs Tokens:", error);
      });
  },
  // OutputSizeVsTPOT line chart ============================= /

  // OutputSizeVslatency line chart =============================
  getOutputSizeVsLatency: async (benchmarkId: string) => {
    get()
      .getBenchmarkAnalysisField1VsField2({
        benchmark_id: benchmarkId as string,
        field1: "output_len",
        field2: "latency",
      })
      .then((result) => {
        if (result) {
          set({ outputSizeVsLatency: result });
        }
      })
      .catch((error) => {
        console.error("Error fetching TTFT vs Tokens:", error);
      });
  },

  getfilterList: async (params: FilterParams) => {
    const query = new URLSearchParams();

    if (params.page) query.append("page", String(params.page));
    if (params.limit) query.append("limit", String(params.limit));
    if (params.search) query.append("search", String(params.search));
    if (params.model_name) query.append("model_name", params.model_name);
    if (params.cluster_name) query.append("cluster_name", params.cluster_name);
    if (params.resource) query.append("resource", params.resource);

    const response: any = await AppRequest.Get(
      `${tempApiBaseUrl}/benchmark/filters?${query.toString()}`,
    );
    if (params.resource == "model") {
      set({ modelFilterList: response?.data?.result });
    } else {
      set({ clusterFilterList: response?.data?.result });
    }
    return response?.data;
  },
  // OutputSizeVslatency line chart ============================= /
}));
