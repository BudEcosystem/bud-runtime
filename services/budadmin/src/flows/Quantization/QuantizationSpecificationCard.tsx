import { useDeployModel } from "src/stores/useDeployModel";
import SelectedModeInfoCard from "../components/SelectedModeInfoCard";
import { SpecificationTableItemProps } from "../components/SpecificationTableItem";
import { useEffect, useState } from "react";
import { useWorkflow } from "src/stores/useWorkflow";

export default function QuantizationSpecificationCard() {
  const { quantizationWorkflow, setQuantizationWorkflow, currentWorkflow } =
    useDeployModel();
  let [specifications, setSpecifcations] = useState([]);

  useEffect(() => {
    if (!currentWorkflow) {
      return;
    }
    setQuantizationWorkflow({
      modelName:
        currentWorkflow.workflow_steps.quantization_config.quantized_model_name,
      type: currentWorkflow.workflow_steps.quantization_config.target_type,
      hardware:
        currentWorkflow.workflow_steps.quantization_config.target_device,
      method: currentWorkflow.workflow_steps.quantization_config.method,
      weight: currentWorkflow.workflow_steps.quantization_config.weight_config
        ? currentWorkflow.workflow_steps.quantization_config.weight_config
        : quantizationWorkflow?.weight,
      activation: currentWorkflow.workflow_steps.quantization_config
        .activation_config
        ? currentWorkflow.workflow_steps.quantization_config.activation_config
        : quantizationWorkflow?.activation,
      clusterId: currentWorkflow.workflow_steps.quantization_config.cluster_id,
    });
  }, [currentWorkflow]);

  const addSpecification = (
    name: string,
    value: string,
    icon: string,
    full: boolean = false,
  ) => {
    specifications.push({
      name: name,
      value: value,
      icon: icon,
      full: full,
      // fullText: true,
    });
  };

  const updateSpecification = () => {
    if (!quantizationWorkflow) {
      return;
    }
    specifications = [];
    addSpecification(
      "Model name",
      quantizationWorkflow.modelName,
      "/images/drawer/disk.png",
      true,
    );
    if (quantizationWorkflow.type) {
      // addSpecification("Type", quantizationWorkflow.type, "/images/drawer/template-1.png")
      addSpecification(
        "Type",
        quantizationWorkflow.type,
        "/images/drawer/template-1.png",
        true,
      );
      // edits made to fix ui issue
    }
    if (quantizationWorkflow.method) {
      addSpecification(
        "Method",
        quantizationWorkflow.method,
        "/images/drawer/template-1.png",
        true,
      );
    }
    setSpecifcations(specifications);
  };

  useEffect(() => {
    updateSpecification();
  }, [quantizationWorkflow]);

  useEffect(() => {
    console.log("specifications", specifications);
  }, [specifications]);

  return (
    <SelectedModeInfoCard
      specTitle="Specification"
      specifications={specifications}
    />
  );
}
