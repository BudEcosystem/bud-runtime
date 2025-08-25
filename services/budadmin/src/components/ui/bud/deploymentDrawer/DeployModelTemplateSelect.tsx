import { Checkbox } from "antd";
import React, { useEffect } from "react";
import { PrimaryButton } from "../form/Buttons";
import { Image } from "antd";
import { Text_10_400_B3B3B3, Text_14_400_EEEEEE } from "../../text";
import { useDeployModel } from "src/stores/useDeployModel";
import {
  IDeploymentTemplate,
  useDeploymentTemplates,
} from "src/hooks/useTemplates";
import { assetBaseUrl } from "@/components/environment";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import { useDrawer } from "src/hooks/useDrawer";

function ModelCard({
  selected,
  handleClick,
  data,
}: {
  selected?: boolean;
  handleClick?: () => void;
  data: IDeploymentTemplate;
}) {
  const [hover, setHover] = React.useState(false);

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onClick={handleClick}
      onMouseLeave={() => setHover(false)}
      className="py-[1.1rem] hover:bg-[#FFFFFF03] cursor-pointer hover:shadow-lg px-[1.4rem] border-b-[0.5px] border-t-[0.5px] border-t-[transparent] border-b-[#1F1F1F] hover:border-t-[.5px] hover:border-[#757575] flex-row flex border-box"
    >
      <div className="mr-[.7rem]">
        <div className="bg-[#1F1F1F] w-[1.75rem] h-[1.75rem] rounded-[5px] flex justify-center items-center  shrink-0 grow-0">
          <Image
            preview={false}
            src={assetBaseUrl + data.icon}
            className="!w-[1.25rem] !h-[1.25rem]"
            style={{ width: "1.25rem", height: "1.25rem" }}
            alt="home"
          />
        </div>
      </div>
      <div className="flex justify-between w-full flex-col">
        <div className="flex items-center justify-between h-4">
          <div className="flex ">
            <Text_14_400_EEEEEE className="leading-[150%] up">
              {data.name}
            </Text_14_400_EEEEEE>
          </div>
          <div
            style={{
              display: hover || selected ? "flex" : "none",
            }}
          >
            <Checkbox
              checked={selected}
              className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem] mt-[.85rem]"
            />
          </div>
        </div>
        <Text_10_400_B3B3B3 className="overflow-hidden trunicate leading-[170%]">
          {data.description || "-"}
        </Text_10_400_B3B3B3>
      </div>
    </div>
  );
}

function DeployModelTemplateSelect() {
  const [page, setPage] = React.useState(1);
  const [limit, setLimit] = React.useState(1000);
  const { openDrawerWithStep } = useDrawer();
  const { getTemplates, deploymentTemplates } = useDeploymentTemplates();
  const [search, setSearch] = React.useState("");
  const {
    currentWorkflow,
    selectedTemplate,
    setSelectedTemplate,
    updateTemplate,
    setDeploymentSpecification,
    deploymentSpecifcation,
  } = useDeployModel();

  useEffect(() => {
    getTemplates({ page, limit });
  }, []);

  useEffect(() => {
    if (currentWorkflow?.workflow_steps?.model) {
      // setSelectedTemplate(currentWorkflow.workflow_steps.template);
    }
  }, [currentWorkflow]);

  useEffect(() => {
    console.log("currentWorkflow", currentWorkflow);
  }, [currentWorkflow]);

  const filteredDeploymentTemplates = deploymentTemplates.filter(({ name }) => {
    return name?.toLowerCase().includes(search.toLowerCase());
  });

  return (
    <div>
      <div className="px-[1.4rem] pt-[1rem] rounded-es-lg rounded-ee-lg pb-[.4rem]">
        <div className="flex items-center justify-between gap-[.7rem]">
          <SearchHeaderInput
            placeholder="Search Templates"
            searchValue={search}
            setSearchValue={setSearch}
            expanded
          />
          <PrimaryButton
            classNames=""
            onClick={async () => {
              // openDrawer("create-template");
              const template = deploymentTemplates.find((template) => {
                return template.name?.toLowerCase() === "other";
              });
              setSelectedTemplate(template);
              setDeploymentSpecification({
                deployment_name: deploymentSpecifcation.deployment_name,
                concurrent_requests: deploymentSpecifcation.concurrent_requests,
                avg_context_length: 30,
                avg_sequence_length: 10,
                ...template,
              });
              await updateTemplate();
              openDrawerWithStep("deploy-model-specification");
            }}
          >
            +&nbsp;Create
          </PrimaryButton>
        </div>
      </div>
      <div className="pt-[.6rem]">
        {filteredDeploymentTemplates.map((template, index) => (
          <ModelCard
            key={index}
            data={template}
            selected={selectedTemplate?.id === template.id}
            handleClick={() => {
              setSelectedTemplate(template);
              setDeploymentSpecification({
                deployment_name: deploymentSpecifcation.deployment_name,
                concurrent_requests: deploymentSpecifcation.concurrent_requests,
                ...template,
              });
            }}
          />
        ))}
      </div>
    </div>
  );
}

export default DeployModelTemplateSelect;
