import React from "react";
import { ModelDetailContent } from "@/components/ModelDetailDrawer";
import { useModels } from "@/hooks/useModels";
import { useDrawer } from "@/hooks/useDrawer";

const ViewModelDetails: React.FC = () => {
  const { selectedModel } = useModels();
  const { closeDrawer } = useDrawer();

  if (!selectedModel) {
    return <div>No model selected</div>;
  }

  return <ModelDetailContent model={selectedModel} onClose={closeDrawer} />;
};

export default ViewModelDetails;
