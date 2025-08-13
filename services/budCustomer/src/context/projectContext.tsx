"use client";

import React, { createContext, useContext, useState, useEffect } from "react";

export interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  user_id: string;
  project_type: "client_app" | "existing_app";
  status: "active" | "inactive" | "archived";
  resources: {
    api_keys: number;
    batches: number;
    logs: number;
    models: number;
  };
  color: string;
}

interface ProjectContextType {
  currentProject: Project | null;
  projects: Project[];
  setCurrentProject: (project: Project | null) => void;
  setProjects: (projects: Project[]) => void;
  addProject: (project: Project) => void;
  updateProject: (projectId: string, updates: Partial<Project>) => void;
  deleteProject: (projectId: string) => void;
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

export const useProject = () => {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error("useProject must be used within a ProjectProvider");
  }
  return context;
};

interface ProjectProviderProps {
  children: React.ReactNode;
}

export const ProjectProvider: React.FC<ProjectProviderProps> = ({
  children,
}) => {
  const [currentProject, setCurrentProject] = useState<Project | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);

  // Load projects and current project from localStorage on mount
  useEffect(() => {
    if (typeof window === "undefined") return;

    const savedProjects = localStorage.getItem("bud_projects");
    if (savedProjects) {
      const parsedProjects = JSON.parse(savedProjects);
      setProjects(parsedProjects);

      // Set the first active project as current if none is selected
      const savedCurrentProject = localStorage.getItem("bud_current_project");
      if (savedCurrentProject) {
        const parsed = JSON.parse(savedCurrentProject);
        const project = parsedProjects.find((p: Project) => p.id === parsed.id);
        if (project && project.status === "active") {
          setCurrentProject(project);
        }
      } else {
        // Auto-select first active project
        const firstActiveProject = parsedProjects.find(
          (p: Project) => p.status === "active",
        );
        if (firstActiveProject) {
          setCurrentProject(firstActiveProject);
        }
      }
    }
  }, []);

  // Save to localStorage when projects change
  useEffect(() => {
    if (typeof window === "undefined") return;
    localStorage.setItem("bud_projects", JSON.stringify(projects));
  }, [projects]);

  // Save current project to localStorage when it changes
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (currentProject) {
      localStorage.setItem(
        "bud_current_project",
        JSON.stringify(currentProject),
      );
    } else {
      localStorage.removeItem("bud_current_project");
    }
  }, [currentProject]);

  const addProject = (project: Project) => {
    setProjects((prev) => [project, ...prev]);

    // Auto-select new project if it's the first active one
    if (project.status === "active" && !currentProject) {
      setCurrentProject(project);
    }
  };

  const updateProject = (projectId: string, updates: Partial<Project>) => {
    setProjects((prev) =>
      prev.map((project) =>
        project.id === projectId
          ? { ...project, ...updates, updated_at: new Date().toISOString() }
          : project,
      ),
    );

    // Update current project if it's the one being updated
    if (currentProject?.id === projectId) {
      setCurrentProject((prev) =>
        prev
          ? { ...prev, ...updates, updated_at: new Date().toISOString() }
          : null,
      );
    }

    // Clear current project if it becomes inactive/archived
    if (
      currentProject?.id === projectId &&
      updates.status &&
      updates.status !== "active"
    ) {
      const activeProjects = projects.filter(
        (p) => p.status === "active" && p.id !== projectId,
      );
      setCurrentProject(activeProjects.length > 0 ? activeProjects[0] : null);
    }
  };

  const deleteProject = (projectId: string) => {
    setProjects((prev) => prev.filter((project) => project.id !== projectId));

    // Clear current project if it's being deleted
    if (currentProject?.id === projectId) {
      const remainingProjects = projects.filter(
        (p) => p.id !== projectId && p.status === "active",
      );
      setCurrentProject(
        remainingProjects.length > 0 ? remainingProjects[0] : null,
      );
    }
  };

  const value: ProjectContextType = {
    currentProject,
    projects,
    setCurrentProject,
    setProjects,
    addProject,
    updateProject,
    deleteProject,
  };

  return (
    <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>
  );
};
