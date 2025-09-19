import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { useDrawer } from "src/hooks/useDrawer";
import SelectedModeInfoCard from "../components/SelectedModeInfoCard";
import search from "antd/es/transfer/search";
import ProviderCardWithCheckBox from "../components/ProviderCardWithCheckBox";
import SearchHeaderInput from "../components/SearchHeaderInput";
import QuantizationMethodCard from "../components/QuantizationMethodCard";
import { useDeployModel } from "src/stores/useDeployModel";
import { useContext, useEffect } from "react";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import React from "react";
import QuantizationSpecificationCard from "./QuantizationSpecificationCard";

export default function QuantizationMethod() {
  const { openDrawerWithStep } = useDrawer();
  const {
    updateQuantizationMethod,
    setQuantizationWorkflow,
    quantizationWorkflow,
    getQuantizationMethods,
    quantizationMethods,
    updateQuantizationAdvanced,
  } = useDeployModel();
  const { values, form } = useContext(BudFormContext);

  const [search, setSearch] = React.useState("");

  useEffect(() => {
    getQuantizationMethods();
  }, []);

  // const quantizationMethods = [
  //     { id: "dynamic", name: "RTN", description: "RTN is a quantization method that uses a rounding technique to quantize the weights and activations.", hardware_support: ["CPU", "CUDA"], method_type: ["INT8", "INT4"], runtime_hardware_support: ["CPU", "CUDA"] },
  //     { id: "dynamic", name: "dynamic", description: "QAT is a quantization method that uses a quantization technique to quantize the weights and activations.", hardware_support: ["CUDA"], method_type: ["INT8", "INT4"], runtime_hardware_support: ["CUDA"] },
  //     { id: "static", name: "static", description: "DoReFa is a quantization method that uses a dynamic range technique to quantize the weights and activations.", hardware_support: ["CPU", "CUDA"], method_type: ["INT8"], runtime_hardware_support: ["CPU", "CUDA"] },
  // ];

  const selectMethod = (value) => {
    setQuantizationWorkflow({ ...quantizationWorkflow, method: value.name });
  };

  const filteredMethods = quantizationMethods?.filter(
    (method) =>
      method.name.toLowerCase().includes(search.toLowerCase()) &&
      method.hardware_support.includes(
        quantizationWorkflow?.hardware?.toUpperCase(),
      ) &&
      method.method_type.includes(quantizationWorkflow?.type?.toUpperCase()),
  );

  const typeItems = [
    { label: "INT8", value: 8 },
    { label: "INT4", value: 4 },
    { label: "INT2", value: 2 },
  ];

  const handleNext = async () => {
    const result = await updateQuantizationMethod(quantizationWorkflow.method);
    if (!result) {
      return;
    }
    let selectedBit = typeItems.find(
      (item) => item.label === quantizationWorkflow?.type,
    );
    quantizationWorkflow.weight = {
      bit: selectedBit?.value,
      granularity: "per_channel",
      symmetric: true,
    };
    quantizationWorkflow.activation = {
      bit: selectedBit?.value,
      granularity: "per_token",
      symmetric: true,
    };
    const result_advanced = await updateQuantizationAdvanced(
      quantizationWorkflow.weight,
      quantizationWorkflow.activation,
    );
    if (!result_advanced) {
      return;
    }
    openDrawerWithStep("quantization-simulation-status");
    // openDrawerWithStep("advanced-settings")
  };

  return (
    <BudForm
      data={quantizationWorkflow}
      onBack={() => {
        openDrawerWithStep("quantization-detail");
      }}
      disableNext={!quantizationWorkflow?.method}
      onNext={handleNext}
    >
      <BudWraperBox>
        <QuantizationSpecificationCard />
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Quantization method"
            description="Pick one method based on your accuracy and performance requirements"
            classNames="border-[0] border-b-[.5px]"
          />
          <div className="px-[1.5rem] mt-[1.5rem]">
            <SearchHeaderInput
              placeholder="Search methods"
              searchValue={search}
              setSearchValue={setSearch}
              expanded
              // expanded searchValue={""} setSearchValue={function (value: string): void {
              //     throw new Error("Function not implemented.");
              // } }
            />
          </div>
          <div className="pt-[.4rem]">
            {filteredMethods?.map((item, index) => (
              <QuantizationMethodCard
                key={index}
                data={item}
                selected={quantizationWorkflow?.method === item.name}
                handleClick={() => {
                  selectMethod(item);
                }}
              />
            ))}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
