import { create } from "zustand";
import { Tag } from "@/components/ui/bud/dataEntry/TagsInput";
import { Cluster } from "./useCluster";

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
    // Stub implementation
    return Promise.resolve({ projects: [], total_record: 0, total_pages: 0 });
  },

  getProjectTags: async () => {
    // Stub implementation
  },

  getGlobalProjects: async (page: any, limit: any, search?: string) => {
    // Stub implementation
  },

  createProject: async (data: any): Promise<any> => {
    // Stub implementation
    return Promise.resolve({});
  },

  deleteProject: async (projectId: string, router: any): Promise<any> => {
    // Stub implementation
    return Promise.resolve({});
  },

  updateProject: async (projectId: string, data: any) => {
    // Stub implementation
    return Promise.resolve({});
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
    // Stub implementation
  },

  getProject: async (projectId) => {
    // Stub implementation
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
