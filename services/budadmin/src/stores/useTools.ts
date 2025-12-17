import { create } from "zustand";

export interface Tool {
  id: string;
  name: string;
  icon: string;
  category: string;
  description: string;
  tags: { name: string; color: string }[];
  created_at: string;
  usage_count: number;
  subTools?: SubTool[];
}

export interface SubTool {
  id: string;
  name: string;
  description: string;
}

interface ToolsState {
  tools: Tool[];
  selectedTool: Tool | null;
  isLoading: boolean;

  // Actions
  setTools: (tools: Tool[]) => void;
  setSelectedTool: (tool: Tool | null) => void;
  getTools: () => Promise<void>;
  getTool: (id: string) => Promise<Tool | null>;
}

export const useTools = create<ToolsState>((set, get) => ({
  tools: [],
  selectedTool: null,
  isLoading: false,

  setTools: (tools) => set({ tools }),

  setSelectedTool: (tool) => set({ selectedTool: tool }),

  getTools: async () => {
    set({ isLoading: true });
    try {
      // TODO: Replace with actual API call
      // const response = await AppRequest.Get("/tools");
      // set({ tools: response.data });

      // Mock data for now
      const mockTools: Tool[] = [
        {
          id: "1",
          name: "Tool 1",
          icon: "🔧",
          category: "Category",
          description: "One sentence description",
          tags: [
            { name: "Tag 1", color: "#965CDE" },
            { name: "tool", color: "#3B82F6" },
          ],
          created_at: new Date().toISOString(),
          usage_count: 12,
        },
        {
          id: "2",
          name: "Tool 1",
          icon: "⚙️",
          category: "Category",
          description: "One sentence description",
          tags: [
            { name: "Tag 2", color: "#22C55E" },
            { name: "tool", color: "#3B82F6" },
          ],
          created_at: new Date().toISOString(),
          usage_count: 8,
        },
        {
          id: "3",
          name: "Tool 1",
          icon: "🛠️",
          category: "Category",
          description: "One sentence description",
          tags: [{ name: "tag 3", color: "#F59E0B" }],
          created_at: new Date().toISOString(),
          usage_count: 5,
        },
        {
          id: "4",
          name: "Virtual tool 1",
          icon: "🖥️",
          category: "Category",
          description: "One sentence description",
          tags: [
            { name: "virtual", color: "#EF4444" },
            { name: "tool", color: "#3B82F6" },
          ],
          created_at: new Date().toISOString(),
          usage_count: 3,
        },
      ];
      set({ tools: mockTools });
    } catch (error) {
      console.error("Error fetching tools:", error);
    } finally {
      set({ isLoading: false });
    }
  },

  getTool: async (id: string) => {
    set({ isLoading: true });
    try {
      // TODO: Replace with actual API call
      // const response = await AppRequest.Get(`/tools/${id}`);
      // set({ selectedTool: response.data });
      // return response.data;

      // Mock data for now - find from existing tools or create mock
      const { tools } = get();
      const tool = tools.find((t) => t.id === id);
      if (tool) {
        set({ selectedTool: tool });
        return tool;
      }
      return null;
    } catch (error) {
      console.error("Error fetching tool:", error);
      return null;
    } finally {
      set({ isLoading: false });
    }
  },
}));
