import React from "react";
import { ProjectDetailContent } from "@/components/ProjectDetailDrawer";
import { useProjects } from "@/hooks/useProjects";
import { useDrawer } from "@/hooks/useDrawer";

const ViewProjectDetails: React.FC = () => {
  const { globalSelectedProject } = useProjects();
  const { closeDrawer } = useDrawer();

  // Handle both nested and direct project structure
  const projectId =
    globalSelectedProject?.project?.id || (globalSelectedProject as any)?.id;

  if (!projectId) {
    return <div>No project selected</div>;
  }

  return <ProjectDetailContent projectId={projectId} onClose={closeDrawer} />;
};

export default ViewProjectDetails;
