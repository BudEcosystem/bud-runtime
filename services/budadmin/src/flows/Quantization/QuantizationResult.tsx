import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import QuantizationSpecificationCard from "./QuantizationSpecificationCard";
import { useDrawer } from "src/hooks/useDrawer";
import { useDeployModel } from "src/stores/useDeployModel";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Text_12_400_757575, Text_12_400_B3B3B3, Text_12_400_EEEEEE } from "@/components/ui/text";
import { ConfigProvider, Progress } from "antd";
import GuageChart from "@/components/charts/GuageChart";
import { useEffect } from "react";


function PerformanceItem({
    label,
    value
}: {
    label: string;
    value: number;
}) {

    return (
        <div className="w-[50%] flex items-center justify-start mb-[0.2rem]">
            <div className="w-[100%] flex justify-start align-center">
                <Text_12_400_B3B3B3 className="ml-[.4rem]">
                    {label}
                </Text_12_400_B3B3B3>
            </div>
            <div className="w-[55px] flex flex-shrink-0 justify-start items-center">
                <div className={`text-align-center font-[400] text-[0.625rem] px-[.2rem] py-[.15rem] px-[.8rem] rounded-[6px] bg-[#D1B85433] text-[#D1B854]`}>
                    {value}
                </div>
            </div>
        </div>
    )
}

export default function QuantizationResult() {

    const { openDrawerWithStep, openDrawer } = useDrawer();
    const { quantizationWorkflow, getWorkflow, currentWorkflow, setSelectedModel } = useDeployModel();

    useEffect(() => {
        getWorkflow();
    }, []);

    const handleNext = () => {
        setSelectedModel(currentWorkflow?.workflow_steps?.quantization_config?.quantized_model);
        openDrawer("view-model");
    }

    return <BudForm
    data={quantizationWorkflow}
    onBack={() => {
        openDrawerWithStep("advanced-settings");
    }}
    disableNext={!quantizationWorkflow?.clusterId}
    onNext={handleNext}
    nextText="View Model"
    >
        <BudWraperBox>
            <QuantizationSpecificationCard />
            <BudDrawerLayout>
                <DrawerTitleCard
                    title="Quantization Success"
                    description="The model is successfully quantised. Here is the result of the evaluation. If the results are good, you can add the model to the registry."
                    classNames="border-[0] border-b-[.5px]"
                />
                <div className="flex flex-wrap justify-between w-full my-[1.5rem] px-[.75rem] pt-[0rem] pb-[.2rem]">
                    <PerformanceItem label="Quantization perplexity" value={10} />
                    <PerformanceItem label="Base perplexity" value={9.6} />
                </div>
                <DrawerTitleCard
                    title="Evaluation Deviation"
                    description="Accuracy deviation from the base model"
                    classNames="border-[0] border-b-[.5px]"
                />

                <div className="h-[220px] my-[1rem] mb-[2.5rem]">
                    <GuageChart
                    data={{
                        percentage: 96,
                        tag: 'Low Deviation',
                        reverse: true
                        }}
                    />
                </div>
            </BudDrawerLayout>
        </BudWraperBox>
    </BudForm>
}
