import { successToast } from "@/components/toast";
import { AppRequest } from "@/services/api/requests";
import { create } from "zustand";

export enum PermissionEnum {
  ModelView = "model:view",
  ModelManage = "model:manage",
  ModelBenchmark = "model:benchmark",
  ProjectView = "project:view",
  ProjectManage = "project:manage",
  ClusterView = "cluster:view",
  ClusterManage = "cluster:manage",
  UserManage = "user:manage",
  UserView = "user:view",
  EndpointView = "endpoint:view",
  EndpointManage = "endpoint:manage",
  BenchmarkView = "benchmark:view",
  BenchmarkManage = "benchmark:manage",
}

type Permission = {
  name: PermissionEnum;
  has_permission: boolean;
};

type ModulePermission = {
  rsid: string;
  rsname: string;
  scopes: string[];
};

type UserParams = {
  name?: string;
  password?: string;
  role?: string[];
};

type GlobalScopes = Permission[];

type ProjectScopes = {
  id: string;
  permissions: Permission[];
  name: string;
};

export const useUser = create<{
  loadingUser: boolean;
  user: any;
  setUser: (user: any) => void;
  updateCurrentUser: (params: UserParams, id: string) => Promise<any>;
  getUser: () => Promise<any>;
  logout: () => Promise<void>;
  permissions: ModulePermission[];
  hasPermission: (permission: PermissionEnum) => boolean;
  hasProjectPermission: (
    projectId: string,
    permission: PermissionEnum,
  ) => boolean;
}>((set, get) => ({
  loadingUser: true,
  user: null,
  setUser: (user) => set(() => ({ user })),
  getUser: async () => {
    set(() => ({ loadingUser: true }));
    const response: any = await AppRequest.Get(`/users/me`);
    set(() => ({ user: response.data?.user }));
    const permissions = await AppRequest.Get(`/users/me/permissions`);
    set(() => ({ permissions: permissions.data?.permissions }));
    set(() => ({ loadingUser: false }));
    return response;
  },
  logout: async () => {
    try {
      // Get the refresh token before clearing
      const refreshToken = localStorage.getItem("refresh_token");

      // Call logout API if refresh token exists
      if (refreshToken) {
        await AppRequest.Post("/auth/logout", {
          refresh_token: refreshToken,
        });
      }
    } catch (error) {
      console.error("Logout API error:", error);
      // Continue with local cleanup even if API call fails
    } finally {
      // Clear all auth data
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("bud_current_project");
      localStorage.removeItem("bud_projects");

      // Reset user state
      set(() => ({ user: null, permissions: [], loadingUser: false }));

      // Redirect to login
      if (typeof window !== "undefined") {
        window.location.replace("/login");
      }
    }
  },
  permissions: [],
  hasPermission: (permission: PermissionEnum) => {
    const [module, scope] = permission.split(":");

    // Find the module in permissions array
    const modulePermission = get().permissions?.find(
      (p) => p.rsname === `module_${module}`,
    );

    // Check if the module exists and has the required scope
    return modulePermission?.scopes.includes(scope) ?? false;
  },

  hasProjectPermission: (projectId: string, permission: PermissionEnum) => {
    return get().permissions?.some(
      (scope) => scope.rsid === projectId && scope.rsname === permission,
    );
  },

  updateCurrentUser: async (params: UserParams, id: string) => {
    try {
      const filteredParams = Object.fromEntries(
        Object.entries(params).filter(
          ([_, value]) => value !== "" && value !== null && value !== undefined,
        ),
      );
      const response: any = await AppRequest.Patch(
        `/users/${id}`,
        filteredParams,
      );
      if (response) {
        get().getUser();
        successToast(response.data.message);
        return true;
      }
      return false;
    } catch (error) {
      console.error("Error updating user:", error);
      return false;
    }
  },
}));
