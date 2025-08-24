import React from "react";
import { ProjectDetailContent } from "@/components/ProjectDetailDrawer";
import { useProjects } from "@/hooks/useProjects";
import { useDrawer } from "@/hooks/useDrawer";

const ViewProjectDetails: React.FC = () => {
  const { selectedProject } = useProjects();
  const { closeDrawer } = useDrawer();

  if (!selectedProject?.project?.id) {
    return <div>No project selected</div>;
  }

  return <ProjectDetailContent projectId={selectedProject.project.id} onClose={closeDrawer} />;
};

export default ViewProjectDetails;
