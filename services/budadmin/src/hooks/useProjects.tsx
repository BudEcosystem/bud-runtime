import { set } from "rc-util";
import { useCallback, useEffect, useState } from "react";
import { successToast } from "../components/toast";
import { AppRequest } from "../pages/api/requests";
import { useLoader } from "../context/appContext";
import { create } from "zustand";
import { useRouter } from "next/router";
import { Tag } from "@/components/ui/bud/dataEntry/TagsInput";
import { Cluster } from "./useCluster";
import { tempApiBaseUrl } from "@/components/environment";
import {
  convertToObservabilityRequest,
  convertObservabilityResponse,
  ObservabilityMetricsResponse,
} from "@/utils/metricsAdapter";

export type Project = {
  id: string;
  name: string;
  description: string;
  tags: Tag[];
  icon: string;
  created_user: {
    name: string;
    email: string;
    id: string;
    color: string;
    role: string;
  };
  created_at: string;
  endpoints_count: number;
  project?: any;
};

export interface IProject {
  project: Project;
  users_count: number;
  endpoints_count: number;
  profile_colors: string[];
}

export type Scopes =
  | "endpoint:view"
  | "endpoint:manage"
  | "project:view"
  | "project:manage";

export type InviteUser = {
  user_id?: string;
  email?: string;
  scopes: Scopes[];
};

type Permission = {
  name: Scopes;
  has_permission: boolean;
};

export type ProjectMember = {
  id: string;
  email: string;
  name: string;
  color: string;
  role: string;
  permissions: Permission[];
  project_role: "owner" | "participant";
  status: string;
};
export type ProjectTags = {
  name: string;
  color: string;
};

export const useProjects = create<{
  projects: Project[];
  projectTags: ProjectTags[];
  totalProjects: number;
  loading: boolean;
  selectedProjectId: string;
  projectMetricsData: any;
  averageMetricsData: any;
  concurrentMetricsData: any;
  ttftMetricsData: any;
  latencyMetricsData: any;
  throughputMetricsData: any;
  selectedProject: Project | null;
  getProjects: (page: any, limit: any, search?: string) => Promise<any>;
  createProject: (data: any) => Promise<any>;
  deleteProject: (projectId: string, router: any) => Promise<any>;
  updateProject: (projectId: string, data: any) => Promise<any>;
  inviteMembers: (
    projectId: string,
    data: {
      users: InviteUser[];
    },
    toast?: boolean,
  ) => Promise<any>;
  getProject: (projectId: string) => void;
  getProjectTags: () => void;
  setSelectedProjectId: (projectId: string) => void;
  setSelectedProject: (project: Project) => void;
  projectValues: any;
  setProjectValues: (values: any) => void;
  removeMembers: (projectId: string, userIds: string[]) => Promise<any>;
  getMembers: (projectId: string) => Promise<any>;
  projectMembers: ProjectMember[];
  updatePermissions: (
    projectId: string,
    userId: string,
    scopes: Permission[],
  ) => Promise<any>;
  getClusters: (projectId: string) => Promise<any>;
  projectClusters: Cluster[];
  totalPages: number;
  globalProjects: Project[];
  globalSelectedProject: Project | null;
  getGlobalProjects: (page: any, limit: any, search?: string) => void;
  getGlobalProject: (projectId: string) => void;
  getProjectMetrics: (params: any) => Promise<any>;
  getQueingMetrics: (params: any) => Promise<any>;
  getConcurrentMetrics: (params: any) => Promise<any>;
  getTtftMetrics: (params: any) => Promise<any>;
  getLatencyMetrics: (params: any) => Promise<any>;
  getThroughputMetrics: (params: any) => Promise<any>;
}>((set, get) => ({
  globalProjects: [],
  globalSelectedProject: null,
  projects: [],
  projectTags: [],
  loading: true,
  totalProjects: 0,
  totalPages: 0,
  selectedProjectId: "",
  selectedProject: null,
  projectMetricsData: null,
  averageMetricsData: null,
  concurrentMetricsData: null,
  ttftMetricsData: null,
  latencyMetricsData: null,
  throughputMetricsData: null,
  projectMembers: [],

  setSelectedProject: (project: Project) => {
    set({ selectedProject: project });
  },
  getProjects: async (page: any, limit: any, search?: string) => {
    let url;
    if (search) {
      url = `${tempApiBaseUrl}/projects/?page=${page}&limit=${limit}&search=true&name=${search}&order_by=-created_at`;
    } else {
      url = `${tempApiBaseUrl}/projects/?page=${page}&limit=${limit}&search=false&order_by=-created_at`;
    }
    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(url);
      set({
        projects: response.data.projects,
        totalProjects: response.data.total_record,
        totalPages: response.data.total_pages,
      });
      return response.data;
    } catch (error) {
      console.error("Error creating model:", error);
    } finally {
      set({ loading: false });
    }
  },
  getProjectTags: async () => {
    const url = `${tempApiBaseUrl}/projects/tags?page=1&limit=1000`;
    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(url);
      console.log("response", response);
      set({
        projectTags: response.data.tags,
      });
    } catch (error) {
      console.error("Error creating model:", error);
    } finally {
      set({ loading: false });
    }
  },
  getGlobalProjects: async (page: any, limit: any, search?: string) => {
    let result = await get().getProjects(page, limit, search);
    let updatedListData = result?.projects;
    if (result && result?.page !== 1) {
      updatedListData = [...get().globalProjects, ...updatedListData];
    }
    set({ globalProjects: updatedListData });
  },
  createProject: async (data: any): Promise<any> => {
    try {
      const response: any = await AppRequest.Post("/projects/", data);
      successToast(response.data.message);
      return response.data.project;
    } catch (error) {
      console.error("Error creating model:", error);
    }
  },
  deleteProject: async (projectId: string, router: any): Promise<any> => {
    try {
      const response: any = await AppRequest.Delete(
        `${tempApiBaseUrl}/projects/${projectId}`,
      );
      successToast(response.data.message);
      setTimeout(() => {
        router.back();
      }, 600);
      return response.data;
    } catch (error) {
      // console.error("Error creating model:", error);
      return error;
    }
  },
  updateProject: async (projectId: string, data: any) => {
    try {
      const response: any = await AppRequest.Patch(
        `${tempApiBaseUrl}/projects/${projectId}`,
        data,
      );
      return response;
    } catch (error) {
      console.error("Error creating model:", error);
    }
  },
  inviteMembers: async (
    projectId: string,
    data: any,
    toast: boolean = true,
  ) => {
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/projects/${projectId}/add-users`,
        data,
      );
      if (toast) {
        successToast(response.data.message);
      }
      return response.data;
    } catch (error) {
      console.error("Error creating model:", error);
    }
  },
  getGlobalProject: async (projectId: string) => {
    try {
      const response: any = await AppRequest.Get(
        `${tempApiBaseUrl}/projects/${projectId}`,
      );
      await get().getMembers(projectId);
      set({
        globalSelectedProject: {
          ...response.data?.project,
          endpoints_count: response.data?.endpoints_count,
        },
      });
      successToast(response.message);
    } catch (error) {
      console.error("Error creating model:", error);
    }
  },
  getProject: async (projectId) => {
    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(
        `${tempApiBaseUrl}/projects/${projectId}`,
      );
      await get().getMembers(projectId);
      set({
        selectedProject: {
          ...response.data?.project,
          endpoints_count: response.data?.endpoints_count,
        },
        selectedProjectId: projectId,
      });
      successToast(response.message);
      set({ loading: false });
    } catch (error) {
      console.error("Error creating model:", error);
      set({ loading: false });
    }
  },
  setSelectedProjectId: (projectId: string) => {
    set({ selectedProjectId: projectId });
    get().getProject(projectId);
  },
  projectValues: null,
  setProjectValues: (values: any) => {
    set({ projectValues: values });
  },
  removeMembers: async (projectId: string, userIds: string[]) => {
    try {
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/projects/${projectId}/remove-users`,
        { user_ids: userIds },
      );
      successToast(response.data.message);
      return response.data;
    } catch (error) {
      console.error("Error creating model:", error);
    }
  },
  getMembers: async (projectId: string) => {
    try {
      const response: any = await AppRequest.Get(
        `${tempApiBaseUrl}/projects/${projectId}/users?page=1&limit=10000&search=false`,
      );
      console.log("response", response);
      set({ projectMembers: response.data.users });
    } catch (error) {
      console.error("Error creating model:", error);
    }
  },
  updatePermissions: async (
    projectId: string,
    userId: string,
    permissions: Permission[],
  ) => {
    try {
      const response: any = await AppRequest.Patch(`/permissions/project`, [
        {
          user_id: userId,
          project_id: projectId,
          permissions: permissions,
        },
      ]);
      successToast(response.data.message);
      return response.data;
    } catch (error) {
      console.error("Error creating model:", error);
    }
  },
  getClusters: async (projectId: string) => {
    try {
      const response: any = await AppRequest.Get(
        `${tempApiBaseUrl}/projects/${projectId}/clusters`,
      );
      set({ projectClusters: response.data.clusters });
      return response.data;
    } catch (error) {
      console.error("Error creating model:", error);
    }
  },
  projectClusters: [],

  getProjectMetrics: async (params: any) => {
    try {
      // Convert old params to new observability format
      const observabilityRequest = convertToObservabilityRequest(params);
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/metrics/analytics`,
        observabilityRequest,
      );

      // Convert response to old format for backward compatibility
      const convertedData = convertObservabilityResponse(
        response.data as ObservabilityMetricsResponse,
        params.metrics,
        params.filter_by,
      );

      set({ projectMetricsData: convertedData });
      return convertedData;
    } catch (error) {
      console.error("Error fetching project metrics:", error);
    }
  },
  getQueingMetrics: async (params: any) => {
    try {
      // Convert old params to new observability format
      const observabilityRequest = convertToObservabilityRequest(params);
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/metrics/analytics`,
        observabilityRequest,
      );

      // Convert response to old format for backward compatibility
      const convertedData = convertObservabilityResponse(
        response.data as ObservabilityMetricsResponse,
        params.metrics,
        params.filter_by,
      );

      set({ averageMetricsData: convertedData });
      return convertedData;
    } catch (error) {
      console.error("Error fetching queuing metrics:", error);
    }
  },
  getConcurrentMetrics: async (params: any) => {
    try {
      // Convert old params to new observability format
      const observabilityRequest = convertToObservabilityRequest(params);
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/metrics/analytics`,
        observabilityRequest,
      );

      // Convert response to old format for backward compatibility
      const convertedData = convertObservabilityResponse(
        response.data as ObservabilityMetricsResponse,
        params.metrics,
        params.filter_by,
      );

      set({ concurrentMetricsData: convertedData });
      return convertedData;
    } catch (error) {
      console.error("Error fetching concurrent metrics:", error);
    }
  },
  getTtftMetrics: async (params: any) => {
    try {
      // Convert old params to new observability format
      const observabilityRequest = convertToObservabilityRequest(params);
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/metrics/analytics`,
        observabilityRequest,
      );

      // Convert response to old format for backward compatibility
      const convertedData = convertObservabilityResponse(
        response.data as ObservabilityMetricsResponse,
        params.metrics,
        params.filter_by,
      );

      set({ ttftMetricsData: convertedData });
      return convertedData;
    } catch (error) {
      console.error("Error fetching TTFT metrics:", error);
    }
  },
  getLatencyMetrics: async (params: any) => {
    try {
      // Convert old params to new observability format
      const observabilityRequest = convertToObservabilityRequest(params);
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/metrics/analytics`,
        observabilityRequest,
      );

      // Convert response to old format for backward compatibility
      const convertedData = convertObservabilityResponse(
        response.data as ObservabilityMetricsResponse,
        params.metrics,
        params.filter_by,
      );

      set({ latencyMetricsData: convertedData });
      return convertedData;
    } catch (error) {
      console.error("Error fetching latency metrics:", error);
    }
  },
  getThroughputMetrics: async (params: any) => {
    try {
      // Convert old params to new observability format
      const observabilityRequest = convertToObservabilityRequest(params);
      const response: any = await AppRequest.Post(
        `${tempApiBaseUrl}/metrics/analytics`,
        observabilityRequest,
      );

      // Convert response to old format for backward compatibility
      const convertedData = convertObservabilityResponse(
        response.data as ObservabilityMetricsResponse,
        params.metrics,
        params.filter_by,
      );

      set({ throughputMetricsData: convertedData });
      return convertedData;
    } catch (error) {
      console.error("Error fetching throughput metrics:", error);
    }
  },
}));
