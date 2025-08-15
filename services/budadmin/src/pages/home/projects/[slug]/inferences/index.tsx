import React from 'react';
import InferenceListTable from '@/components/ui/bud/table/InferenceListTable';

interface InferenceListViewProps {
  projectId?: string;
}

const InferenceListView: React.FC<InferenceListViewProps> = ({ projectId }) => {
  return <InferenceListTable projectId={projectId} />;
};

export default InferenceListView;
