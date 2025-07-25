import { useDrawer } from "src/hooks/useDrawer";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import SelectedModeInfoCard from "../components/SelectedModeInfoCard";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import TextInput from "../components/TextInput";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import CustomDropdownMenu, { BudDropdownMenu } from "@/components/ui/dropDown";
import { Text_12_300_EEEEEE, Text_12_400_FFFFFF } from "@/components/ui/text";
import CustomPopover from "../components/customPopover";
import { ConfigProvider, Select, Image } from "antd";
import { useDeployModel } from "src/stores/useDeployModel";
import { useContext, useEffect } from "react";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useModels } from "src/hooks/useModels";

export default function QuantizationDetail() {
    const { openDrawerWithStep, closeDrawer } = useDrawer();
    const { createQuantizationWorkflow, setQuantizationWorkflow, quantizationWorkflow } = useDeployModel();
    const { selectedModel } = useModels();
    const { values, form } = useContext(BudFormContext);

    const typeItems = [
        { label: "INT8", value: "INT8" },
        { label: "INT4", value: "INT4" },
        { label: "INT2", value: "INT2" },
        ];
    const hardwareItems = [
        { label: "CPU", value: "CPU" },
        { label: "GPU", value: "CUDA" },
        ];
    
    const handleNext = async () => {
        form.submit();

        const result = await createQuantizationWorkflow(quantizationWorkflow.modelName, quantizationWorkflow.type, quantizationWorkflow.hardware);
        if (!result) {
            return;
        }
        // setQuantizationWorkflow(values);
        openDrawerWithStep("quantization-method")
    }

    const handleChange = (name: string, value: any) => {
        form.setFieldsValue({ [name]: value });
        form.validateFields([name]);
        setQuantizationWorkflow({ ...quantizationWorkflow, [name]: value });
    }

    useEffect(() => {
        let defaultValues = {
            type: typeItems[0].value,
            hardware: hardwareItems[0].value,
            modelName: selectedModel?.name + '_INT8'
        }
        if(quantizationWorkflow?.type) {
            defaultValues.type = quantizationWorkflow?.type;
        }
        if(quantizationWorkflow?.hardware) {
            defaultValues.hardware = quantizationWorkflow?.hardware;
        }
        if(quantizationWorkflow?.modelName) {
            defaultValues.modelName = quantizationWorkflow?.modelName;
        }
        setQuantizationWorkflow({ ...quantizationWorkflow, ...defaultValues });
    }, [])

    return <BudForm
        data={quantizationWorkflow}
        backText="Back"
        nextText="Next"
        disableNext={!quantizationWorkflow?.modelName}
        onBack={() => {
            closeDrawer()
        }}
        onNext={handleNext}
    >
        <BudWraperBox>
            <SelectedModeInfoCard />
            <BudDrawerLayout>
                <DrawerTitleCard
                    title="Quantization Details"
                    description="Enter the quantization details"
                    classNames="border-[0] border-b-[.5px]"
                />
                <DrawerCard>
                    <TextInput
                        name="modelName"
                        label="Model name"
                        placeholder="Enter Model name"
                        rules={[{ required: true, message: "Please enter Model name" }]}
                        ClassNames="mt-[.4rem]"
                        infoText="Enter a name for the quantized model"
                        onChange={(e) => handleChange("modelName", e)}
                    />
                    <BudDropdownMenu
                        name="type"
                        label="Quantization Type"
                        infoText="Select target quantization type"
                        placeholder="Select quantization type"
                        items={typeItems}
                        onSelect={() => {}}
                        onChange={(e) => handleChange("type", e)}
                    />
                    <BudDropdownMenu
                        name="hardware"
                        label="Quantisation Hardware"
                        infoText="Select hardware to quantise the model"
                        placeholder="Select hardware"
                        items={hardwareItems}
                        onSelect={() => {}}
                        onChange={(e) => handleChange("hardware", e)}
                    />
                </DrawerCard>
            </BudDrawerLayout>
        </BudWraperBox>
    </BudForm>
}