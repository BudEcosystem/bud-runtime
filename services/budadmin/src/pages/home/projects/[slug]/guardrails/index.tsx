import React from "react";
import GuardrailsListTable from "@/components/ui/bud/table/guardrailsListTable";

interface GuardrailsListViewProps {
  projectId?: string;
}

const GuardrailListView: React.FC<GuardrailsListViewProps> = ({ projectId }) => {
  return <GuardrailsListTable projectId={projectId} />;
};

export default GuardrailListView;
