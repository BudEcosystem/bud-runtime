import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard"
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout"
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm"
import { AdapterInfoCard } from "./AdapterInfoCard"
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox"
import DeployModelSelect from "@/components/ui/bud/deploymentDrawer/DeployModelSelect"
import { useModels } from "src/hooks/useModels"
import ModelFilter from "@/components/ui/bud/deploymentDrawer/ModelFilter"
import React, { useContext, useEffect } from "react"
import { useEndPoints } from "src/hooks/useEndPoint"
import { useDeployModel } from "src/stores/useDeployModel"
import { useDrawer } from "src/hooks/useDrawer"
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext"
import { Text_12_300_EEEEEE } from "@/components/ui/text"
import { useRouter } from "next/router"


export const SelectAdapterModel = () => {

    const { fetchModels } = useModels();
    const { clusterDetails } = useEndPoints();
    const { createAddAdapterWorkflow, setAdapterWorkflow, adapterWorkflow } = useDeployModel();
    const { openDrawerWithStep, closeDrawer } = useDrawer();
    const { values, form } = useContext(BudFormContext);

    const [page, setPage] = React.useState(1);
    const [limit, setLimit] = React.useState(10);
    const [models, setModels] = React.useState([]);
    const [search, setSearch] = React.useState("");
    const [selectedModel, setSelectedModel] = React.useState(null);

    const router = useRouter();
    const projectId = router.query.projectId as string;

    useEffect(() => {
        fetchModels({
            page, limit,
            table_source: "model",
            base_model: clusterDetails?.model?.uri,
            base_model_relation: "adapter",
        }).then((data) => {
            setSelectedModel(data.find(item => item.id == adapterWorkflow?.adapterModelId))
            setModels(data);
        });
    }, [page]);

    const filteredModels = models?.filter((model) => {
        return model.name?.toLowerCase().includes(search.toLowerCase()) || model.tags?.some((task) => task?.name?.toLowerCase().includes(search.toLowerCase())) || `${model.model_size}`.includes(search.toLowerCase());
    });

    useEffect(() => {
        console.log("adapterWorkflow", adapterWorkflow);
        if (adapterWorkflow) {
            setSelectedModel(adapterWorkflow.adapterModelId);
        }
    }, [adapterWorkflow]);
    const handleNext = async () => {
        form.submit();

        const result = await createAddAdapterWorkflow(clusterDetails?.id, selectedModel.id, projectId);
        if (!result) {
            return;
        }
        setAdapterWorkflow({ ...adapterWorkflow, "adapterModelId": selectedModel.id });
        openDrawerWithStep("add-adapter-detail")
    }

    return (
        <BudForm
            data={adapterWorkflow}
            nextText="Next"
            onNext={handleNext}
            disableNext={!selectedModel}
            backText="Close"
            onBack={() => { closeDrawer() }}
        >
            <BudWraperBox>
                <AdapterInfoCard />
                <BudDrawerLayout>
                    <DrawerTitleCard title="Select Adapter Model" description="Select the adapter model to add to the endpoint" />
                    <DeployModelSelect
                        models={models}
                        filteredModels={filteredModels}
                        setSelectedModel={setSelectedModel}
                        selectedModel={selectedModel}
                        emptyComponent={
                            <Text_12_300_EEEEEE>
                                No adapter models found
                            </Text_12_300_EEEEEE>
                        }
                    >
                        <ModelFilter
                            search={search}
                            setSearch={setSearch}

                        />
                    </DeployModelSelect>
                </BudDrawerLayout>
            </BudWraperBox>
        </BudForm>
    )
}
