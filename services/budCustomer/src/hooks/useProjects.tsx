import { create } from "zustand";
import { Tag } from "@/components/ui/bud/dataEntry/TagsInput";
import { Cluster } from "./useCluster";
import { AppRequest } from "@/services/api/requests";
import { successToast } from "@/components/toast";

export type ProjectData = {
  id: string;
  name: string;
  description: string;
  tags: Tag[] | null;
  icon: string | null;
  project_type: "client_app" | "existing_app";
  created_by: string;
  created_at: string;
  modified_at: string;
};

export type Project = {
  project: ProjectData;
  users_count: number;
  endpoints_count: number;
  profile_colors: string[];
};

export interface IProject extends Project {}

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
  selectedProject: Project | null;
  getProjects: (page: any, limit: any, search?: string) => Promise<any>;
  createProject: (data: any) => Promise<any>;
  deleteProject: (projectId: string, router: any) => Promise<any>;
  updateProject: (projectId: string, data: any) => Promise<any>;
  inviteMembers: (
    projectId: string,
    data: { users: InviteUser[] },
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
  projectMembers: [],
  projectClusters: [],
  projectValues: null,

  setSelectedProject: (project: Project) => {
    set({ selectedProject: project });
  },

  getProjects: async (page: any, limit: any, search?: string) => {
    let url;
    if (search) {
      url = `/projects/?page=${page}&limit=${limit}&search=true&name=${search}&order_by=-created_at`;
    } else {
      url = `/projects/?page=${page}&limit=${limit}&search=false&order_by=-created_at`;
    }
    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(url);
      set({
        projects: response.data.projects,
        totalProjects: response.data.total_record,
        totalPages: response.data.total_pages
      });
      return response.data;
    } catch (error) {
      console.error("Error fetching projects:", error);
      return { projects: [], total_record: 0, total_pages: 0 };
    } finally {
      set({ loading: false });
    }
  },

  getProjectTags: async () => {
    const url = `/projects/tags?page=1&limit=1000`;
    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(url);
      set({
        projectTags: response.data.tags,
      });
    } catch (error) {
      console.error("Error fetching project tags:", error);
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
      successToast(response.data.message || "Project created successfully");
      return response.data.project;
    } catch (error) {
      console.error("Error creating project:", error);
      throw error;
    }
  },

  deleteProject: async (projectId: string, router: any): Promise<any> => {
    try {
      const response: any = await AppRequest.Delete(`/projects/${projectId}`);
      successToast(response.data.message || "Project deleted successfully");
      if (router) {
        setTimeout(() => {
          router.back();
        }, 600);
      }
      return response.data;
    } catch (error) {
      console.error("Error deleting project:", error);
      throw error;
    }
  },

  updateProject: async (projectId: string, data: any) => {
    try {
      const response: any = await AppRequest.Patch(`/projects/${projectId}`, data);
      successToast(response.data.message || "Project updated successfully");
      return response.data.project;
    } catch (error) {
      console.error("Error updating project:", error);
      throw error;
    }
  },

  inviteMembers: async (
    projectId: string,
    data: any,
    toast: boolean = true,
  ) => {
    // Stub implementation
    return Promise.resolve({});
  },

  getGlobalProject: async (projectId: string) => {
    try {
      const response: any = await AppRequest.Get(`/projects/${projectId}`);
      // Check if response has nested structure or direct project
      const projectData = response.data.project?.project ? response.data.project : response.data;
      set({ globalSelectedProject: projectData });
      return projectData;
    } catch (error) {
      console.error("Error fetching project:", error);
    }
  },

  getProject: async (projectId: string) => {
    try {
      const response: any = await AppRequest.Get(`/projects/${projectId}`);
      // Check if response has nested structure or direct project
      const projectData = response.data.project?.project ? response.data.project : response.data;
      set({ selectedProject: projectData });
      return projectData;
    } catch (error) {
      console.error("Error fetching project:", error);
    }
  },

  setSelectedProjectId: (projectId: string) => {
    set({ selectedProjectId: projectId });
  },

  setProjectValues: (values: any) => {
    set({ projectValues: values });
  },

  removeMembers: async (projectId: string, userIds: string[]) => {
    // Stub implementation
    return Promise.resolve({});
  },

  getMembers: async (projectId: string) => {
    // Stub implementation
    return Promise.resolve({});
  },

  updatePermissions: async (
    projectId: string,
    userId: string,
    permissions: Permission[],
  ) => {
    // Stub implementation
    return Promise.resolve({});
  },

  getClusters: async (projectId: string) => {
    // Stub implementation
    return Promise.resolve({});
  },
}));
