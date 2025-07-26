import { set } from "rc-util";
import { useCallback, useEffect, useState } from "react";
import { successToast } from "../components/toast";
import { AppRequest } from "../pages/api/requests";
import { useLoader } from "../context/appContext";
import { create } from 'zustand';
import { tempApiBaseUrl } from "@/components/environment";
import { convertToObservabilityRequest, convertObservabilityResponse, ObservabilityMetricsResponse } from "@/utils/metricsAdapter";


interface RequestCountsResponse {
  data: any[]; // Replace with the actual data structure
  message: string;
}

interface GetRequestCountsParams {
  frequency: string;
  filter_by: string;
  filter_conditions?: string[] | null;
  from_date: string;
  to_date?: string | null;
  top_k?: number | null;
  metrics?: string | null;
}


export const useCharts = create<
  {
    accuracyData: any;
    tokenMetrics: any;
    requestCounts: any;
    loading: boolean;
    throughputCount: any;
    latencyCount: any;
    dashboardCount: any;
    totalRequests: any;
    modelCounts: any;
    getRequestCounts: (params: GetRequestCountsParams) => Promise<void>;
    getThroughputAndLatencyData: (params: GetRequestCountsParams) => Promise<void>;
    getDashboardCountData: () => Promise<any>;
    getTotalRequests: (params) => Promise<any>;
    getAccuracyChart: (params) => Promise<any>;
  }
>((set, get) => ({
  accuracyData: null,
  requestCounts: null,
  tokenMetrics: null,
  throughputCount: null,
  latencyCount: null,
  dashboardCount: null,
  loading: true,
  totalRequests: null,
  modelCounts: null,
  getRequestCounts: async (params: any) => {
    const to_date = params.to_date ?? new Date().toISOString();
    const url = `${tempApiBaseUrl}/metrics/analytics`;
    set({ loading: true });
    try {
      // Convert old params to new observability format
      const observabilityRequest = convertToObservabilityRequest({ ...params, to_date });
      const response: any = await AppRequest.Post(url, observabilityRequest);

      // Convert response to old format for backward compatibility
      const convertedData = convertObservabilityResponse(
        response.data as ObservabilityMetricsResponse,
        params.metrics,
        params.filter_by
      );

      set(params.filter_by === 'project' ? { requestCounts: convertedData } : params.metrics == 'input_output_tokens' ? {tokenMetrics : convertedData}: { modelCounts: convertedData });
      successToast(response.message);
    } catch (error) {
      console.error("Error fetching metrics:", error);
    } finally {
      set({ loading: false });
    }
  },
  getThroughputAndLatencyData: async (params: any) => {
    const to_date = params.to_date ?? new Date().toISOString();
    const url = `${tempApiBaseUrl}/metrics/analytics`;
    set({ loading: true });
    try {
      // Convert old params to new observability format
      const observabilityRequest = convertToObservabilityRequest({ ...params, to_date });
      const response: any = await AppRequest.Post(url, observabilityRequest);

      // Convert response to old format for backward compatibility
      const convertedData = convertObservabilityResponse(
        response.data as ObservabilityMetricsResponse,
        params.metrics,
        params.filter_by
      );

      set(params.metrics === 'throughput' ? { throughputCount: convertedData } : { latencyCount: convertedData });
      successToast(response.message);
    } catch (error) {
      console.error("Error fetching performance metrics:", error);
    } finally {
      set({ loading: false });
    }
  },
  getDashboardCountData: async () => {
    const url = `${tempApiBaseUrl}/metrics/count`;
    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(url);
      const listData = response.data;
      set({ dashboardCount: listData });
      successToast(response.message);
    } catch (error) {
      console.error("Error creating model:", error);
    } finally {
      set({ loading: false });
    }
  },
  getTotalRequests: async (params) => {
    const to_date = params.to_date ?? new Date().toISOString();
    const url = `${tempApiBaseUrl}/metrics/analytics`;
    set({ loading: true });
    try {
      // Convert old params to new observability format
      const observabilityRequest = convertToObservabilityRequest({ ...params, to_date });
      const response: any = await AppRequest.Post(url, observabilityRequest);

      // Convert response to old format for backward compatibility
      const convertedData = convertObservabilityResponse(
        response.data as ObservabilityMetricsResponse,
        params.metrics,
        params.filter_by
      );

      set({ totalRequests: convertedData });
      successToast(response.message);
    } catch (error) {
      console.error("Error fetching total requests:", error);
    } finally {
      set({ loading: false });
    }
  },

  getAccuracyChart: async (params) => {
    // const url = `${tempApiBaseUrl}/models/top-leaderboards\\`, {};
    set({ loading: true });
    try {
      const response: any = await AppRequest.Post(`${tempApiBaseUrl}/models/top-leaderboards`, {
        // params: {
        //     benchmarks: params.benchmarks,
        //     k: params.k,
        // },
        benchmarks: params.benchmarks,
        k: params.k,
      });
      const listData = response.data;
      set({ accuracyData: listData.leaderboards });
      // set({ totalRequests: listData.global_metrics });
      successToast(response.message);
    } catch (error) {
      console.error("Error creating model:", error);
    } finally {
      set({ loading: false });
    }
  },

}));
