import { create } from 'zustand';

export type User = {
  id: string;
  name: string;
  email: string;
  color?: string;
  role?: string;
};

export const useUsers = create<{
  users: User[];
  loading: boolean;
  getUsers: (params?: { page?: number; limit?: number; search?: boolean | string }) => Promise<User[]>;
}>((set, get) => ({
  users: [],
  loading: false,
  getUsers: async (params?: { page?: number; limit?: number; search?: boolean | string }) => {
    set({ loading: true });
    
    try {
      // Mock implementation - replace with actual API call
      const mockUsers: User[] = [
        {
          id: '1',
          name: 'John Doe',
          email: 'john.doe@example.com',
          color: '#965CDE',
          role: 'admin'
        },
        {
          id: '2',
          name: 'Jane Smith',
          email: 'jane.smith@example.com',
          color: '#4CAF50',
          role: 'user'
        }
      ];

      // Filter by search if provided
      const searchTerm = typeof params?.search === 'string' ? params.search : '';
      const filteredUsers = searchTerm 
        ? mockUsers.filter(user => 
            user.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            user.email.toLowerCase().includes(searchTerm.toLowerCase())
          )
        : mockUsers;

      set({ users: filteredUsers, loading: false });
      return filteredUsers;
    } catch (error) {
      console.error('Error fetching users:', error);
      set({ loading: false });
      return [];
    }
  },
}));