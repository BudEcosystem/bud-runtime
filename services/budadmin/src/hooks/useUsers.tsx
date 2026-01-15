import { tempApiBaseUrl } from "@/components/environment";
import { AppRequest } from "src/pages/api/requests";
import { create } from "zustand";
import { Provider } from "./useCloudProviders";



export type User = {
  color: string;
  email: string;
  id: string;
  name: string;
  role: string;
  status: string;
  user_type?: string;
};
export type UserPermission = {
  global_scopes: [];
  project_scopes: [];
};

export type UserRolesTypes = {
  label: string;
  value: string;
};
export const UserRoles: UserRolesTypes[] = [
  { label: "Admin", value: "admin" },
  { label: "Developer", value: "developer" },
  { label: "Devops", value: "devops" },
  { label: "Super_admin", value: "super_admin" },
  { label: "Tester", value: "tester" },
  { label: "User", value: "user" },
];

export const UserStatus: UserRolesTypes[] = [
  { label: "Active", value: "active" },
  { label: "Invited", value: "invited" },
  { label: "Deleted", value: "deleted" },
];
type GetUserParams = {
  page: number;
  limit: number;
  order_by?: string;
  name?: string;
  email?: string;
  role?: string;
  status?: string;
  user_type?: string;
  search?: any
};

export const useUsers = create<{
  loading: boolean;
  totalPages: number;
  totalUsers: number;
  users: User[],
  userDetails: any,
  createdUser: any,
  userPermissions,
  filters: any;
  userUsageData: any;

  getUsers: (parms: GetUserParams) => void;
  setCreatedUser: (data) => void;
  fetchUsers: (params: GetUserParams) => Promise<User[]>;
  getUsersDetails: (Id) => Promise<any>;
  getUsersPermissions: (Id) => void;
  deleteUser: (Id) => Promise<any>;
  setUsersPermissions: (Id, setUsersPermissions) => void;
  updateUser: (Id, payload) => Promise<any>;
  addUser: (payload) => Promise<any>;
  getUserUsage: (userId: string) => Promise<any>;
}>((set, get) => ({
  filters: {},
  totalPages: 0,
  totalUsers: 0,
  users: [],
  userDetails: [],
  createdUser: {},
  userPermissions: [],
  userUsageData: null,
  loading: true,
  setCreatedUser: async (data) => {
    set({ createdUser: data });
  },
  fetchUsers: async (params: GetUserParams) => {
    Object.keys(params)
      .forEach((key) => {
        if (!params[key]) {
          delete params[key];
        }
      });

    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(`/users\\`, {
        params: {
          ...params,
          search: Boolean(params.email),
        }
      });
      set({ totalPages: response.data.total_pages, totalUsers: response.data.total_record });
      const listData = response.data;
      const updatedListData = listData.users
      return updatedListData;
    } catch (error) {
      console.error("Error creating model:", error);
    } finally {
      set({ loading: false });
    }
  },
  getUsers: async (params: GetUserParams,) => {
    let updatedListData = await get().fetchUsers(params);
    if (params.page !== 1) {
      updatedListData = [...get().users, ...updatedListData];
    }
    set({ users: updatedListData, filters: params });
  },

  getUsersDetails: async (Id,) => {
    set({ loading: true });
    const response: any = await AppRequest.Get(`/users/${Id}`);
    let userData = response.data?.user;
    set({ userDetails: userData });
    set({ loading: false });
    if(userData) {
      return userData;
    }
  },

  getUsersPermissions: async (Id,) => {
    const response: any = await AppRequest.Get(`/users/${Id}/permissions`);
    let userData = response.data?.result;
    set({ userPermissions: userData });
  },

  setUsersPermissions: async (Id, userPermissions) => {
    const response: any = await AppRequest.Put(`/permissions/${Id}/global`, userPermissions);
    let userData = response.data?.result;
    if (userData) {
      await get().getUsersPermissions(Id);
    }
    // set({ userPermissions: userData });
  },

  updateUser: async (Id, payload) => {
    const response: any = await AppRequest.Patch(`/users/${Id}`, payload);
    let userData = response.data?.result;
    return userData
  },

  deleteUser: async (Id) => {
    const response: any = await AppRequest.Delete(`/users/${Id}`);
    let userData = response.data?.message;
    return userData
  },

  addUser: async (payload) => {
    const response: any = await AppRequest.Post(`/users/`, payload);
    if (response) {
      get().getUsers({ page: 1, limit: 10, order_by: "-created_at" });
    }
    let userData = response?.data;
    return userData
  },

  getUserUsage: async (userId: string) => {
    set({ loading: true });
    try {
      const response: any = await AppRequest.Get(`/billing/user/${userId}/usage`);

      // Extract the actual usage data from the nested response
      const usageData = response?.data?.result || response?.result || null;
      set({ userUsageData: usageData });
      return usageData;
    } catch (error) {
      console.error("Error fetching user usage:", error);
      set({ userUsageData: null });
      throw error;
    } finally {
      set({ loading: false });
    }
  },

}));
