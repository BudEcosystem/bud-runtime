import { BudDrawerLayout } from '@/components/ui/bud/dataEntry/BudDrawerLayout'
import { ModelFlowInfoCard } from '@/components/ui/bud/deploymentDrawer/DeployModelSpecificationInfo'
import React, { useEffect } from 'react'
import { useEndPoints } from 'src/hooks/useEndPoint';

function AddWorkerInfoCard() {
    const { clusterDetails } = useEndPoints();
    const informationSpecs = [
        {
            name: "Deployment Name",
            value: clusterDetails?.name,
            icon: "/images/drawer/tag.png",
            // full: true,
        },
        {
            name: 'Cluster',
            value: clusterDetails?.cluster?.name,
            icon: "/images/drawer/cluster.png",
        },
        {
            name: "Concurrent Request",
            value: clusterDetails?.deployment_config?.concurrent_requests,
            icon: "/images/drawer/current.png",
        },
        {
            name: "Per-session Token/sec",
            value: clusterDetails?.deployment_config?.avg_sequence_length,
            icon: "/images/drawer/per.png",
        },
        {
            name: "End to End Latency",
            value: clusterDetails?.deployment_config?.avg_context_length,
            icon: "/images/drawer/tag.png",
        },
        {
            name: "Time To First Token",
            value: null, // TODO - API
            icon: "/images/drawer/tag.png",
        }
    ]?.filter(obj => obj.value);
    return (
        <BudDrawerLayout>

            <ModelFlowInfoCard
                showTemplate={true}
                selectedModel={clusterDetails?.model}
                deploymentSpecs={informationSpecs}
                deploymentTitle="Deployment Information"

            />
        </BudDrawerLayout>
    )
}

export default AddWorkerInfoCard