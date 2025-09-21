import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { ModelFlowInfoCard } from "@/components/ui/bud/deploymentDrawer/DeployModelSpecificationInfo";
import { useEndPoints } from "src/hooks/useEndPoint";

export const AdapterInfoCard = () => {
  const { clusterDetails } = useEndPoints();

  const informationSpecs = [
    {
      name: "Deployment Name",
      value: clusterDetails?.name,
      icon: "/images/drawer/tag.png",
      full: true,
    },
    {
      name: "Cluster",
      value: clusterDetails?.cluster?.name,
      icon: "/images/drawer/cluster.png",
      full: true,
    },
  ];
  return (
    <BudDrawerLayout>
      <ModelFlowInfoCard
        showTemplate={true}
        selectedModel={clusterDetails?.model}
        deploymentSpecs={informationSpecs}
        deploymentTitle="Deployment Information"
      />
    </BudDrawerLayout>
  );
};
