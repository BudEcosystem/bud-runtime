import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { useDrawer } from "src/hooks/useDrawer";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import TextInput from "../components/TextInput";
import { BudDropdownMenu } from "@/components/ui/dropDown";
import BudSwitch from "@/components/ui/bud/dataEntry/BudSwitch";
import { Text_14_400_EEEEEE } from "@/components/ui/text";
import { title } from "process";
import { useDeployModel } from "src/stores/useDeployModel";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useContext, useEffect } from "react";
import QuantizationSpecificationCard from "./QuantizationSpecificationCard";



export default function AdvancedSettings() {
    const { openDrawerWithStep } = useDrawer();
    const { updateQuantizationAdvanced, setQuantizationWorkflow, quantizationWorkflow } = useDeployModel();
    const { values, form } = useContext(BudFormContext);

    const typeItems = [
        { label: "INT8", value: 8 },
        { label: "INT4", value: 4 },
        { label: "INT2", value: 2 },
        ];

    const granularityItems = [
        { label: "Per Channel", value: "per_channel" },
        { label: "Per Tensor", value: "per_tensor" },
        { label: "Per Group", value: "per_group" },
        { label: "Per Token", value: "per_token" },
        ];

    useEffect(() => {
        console.log(quantizationWorkflow)
        if(!quantizationWorkflow?.weight){
            let selectedBit = typeItems.find(item => item.label === quantizationWorkflow?.type)
            form.setFieldsValue({ weightBit: selectedBit?.value })
            quantizationWorkflow.weight = {
                bit: selectedBit?.value,
                granularity: "per_channel",
                symmetric: true
            }
        }
        if(!quantizationWorkflow?.activation){
            let selectedBit = typeItems.find(item => item.label === quantizationWorkflow?.type)
            form.setFieldsValue({ activationBit: selectedBit?.value })
            quantizationWorkflow.activation = {
                bit: selectedBit?.value,
                granularity: "per_token",
                symmetric: true
            }
        }
        setQuantizationWorkflow({ ...quantizationWorkflow })
    }, [])


    const handleChange = (type: string, name: string, value: any) => {
        console.log(quantizationWorkflow)
        form.setFieldsValue({ [name]: value });
        form.validateFields([name]);
        let config = quantizationWorkflow[type]
        console.log(config)
        if(!config){
            config = {
                bit: '',
                granularity: '',
                symmetric: true
            }
        }
        config[name] = value
        console.log(config)
        setQuantizationWorkflow({ ...quantizationWorkflow, [type]: config });
    }

    const handleNext = async () => {

        const result = await updateQuantizationAdvanced(quantizationWorkflow.weight, quantizationWorkflow.activation);
        if (!result) {
            return;
        }
        openDrawerWithStep("quantization-simulation-status")
    }

    return (
    <BudForm
        data={quantizationWorkflow}
        onBack={() => {
            openDrawerWithStep("quantization-method");
        }}
        disableNext={!quantizationWorkflow?.weight || !quantizationWorkflow?.activation}
        onNext={handleNext}
    >
        <BudWraperBox>
            <QuantizationSpecificationCard />
            <BudDrawerLayout>
                <DrawerTitleCard
                    title="Advanced settings"
                    description="Settings for advanced quantization"
                    classNames="border-[0] border-b-[.5px]"
                />
                <DrawerCard>
                    <div className="flex justify-between align-center mb-[1rem]">
                        <Text_14_400_EEEEEE className="p-0 py-[.4rem] m-0">
                        Weight
                        </Text_14_400_EEEEEE>
                    </div>
                    <BudDropdownMenu
                        name="weightBit"
                        label="Bits"
                        infoText="Select bits required for weight"
                        placeholder="Select bits"
                        items={typeItems}
                        onChange={(e) => handleChange("weight", "bit", e)}
                    />
                    <BudDropdownMenu
                        name="weightGranularity"
                        label="Granularity"
                        infoText="Select granularity"
                        placeholder="Select granularity"
                        items={granularityItems}
                        onChange={(e) => handleChange("weight", "granularity", e)}
                    />
                    <BudSwitch
                        name="weightSymmetric"
                        label="Symmetric"
                        infoText="Enable symmetric quantization"
                        placeholder="Enable"
                        onChange={(e) => handleChange("weight", "symmetric", e)}
                        defaultValue={quantizationWorkflow?.weight?.symmetric}
                    />
                </DrawerCard>
                <DrawerCard>
                    <div className="flex justify-between align-center mb-[1rem]">
                        <Text_14_400_EEEEEE className="p-0 py-[.4rem] m-0">
                        Activation
                        </Text_14_400_EEEEEE>
                    </div>
                    <BudDropdownMenu
                        name="activationBit"
                        label="Bits"
                        infoText="Select bits required for activation"
                        placeholder="Select bits"
                        items={typeItems}
                        onChange={(e) => handleChange("activation", "bit", e)}
                    />
                    <BudDropdownMenu
                        name="activationGranularity"
                        label="Granularity"
                        infoText="Select granularity"
                        placeholder="Select granularity"
                        items={granularityItems}
                        onChange={(e) => handleChange("activation", "granularity", e)}
                    />
                    <BudSwitch
                        name="activationSymmetric"
                        label="Symmetric"
                        infoText="Enable symmetric quantization"
                        placeholder="Enable"
                        onChange={(e) => handleChange("activation", "symmetric", e)}
                        defaultValue={quantizationWorkflow?.activation?.symmetric}
                    />
                </DrawerCard>
            </BudDrawerLayout>
        </BudWraperBox>
    </BudForm>
    )
}
