import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useContext, useEffect } from "react";
import { Text_10_400_757575, Text_12_400_757575, Text_12_400_B3B3B3, Text_12_600_EEEEEE, Text_14_400_EEEEEE } from "@/components/ui/text";
import TextInput from "../components/TextInput";
import FileInput from "../components/FileInput";
import { useWorkflow } from "src/stores/useWorkflow";
import { useCluster } from "src/hooks/useCluster";
import { useDrawer } from "src/hooks/useDrawer";
import { errorToast } from "@/components/toast";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { Tag } from "antd";
import { isValidClusterName, isValidUrl } from "@/lib/utils";
import Tags from "../components/DrawerTags";
import { useDeployModel } from "src/stores/useDeployModel";
import ProjectNameInput from "@/components/ui/bud/dataEntry/ProjectNameInput";

export default function AddCluster() {
  const { submittable, values } = useContext(BudFormContext);
  const [formData, setFormData] = React.useState<FormData>(new FormData());
  const { getWorkflow } = useDeployModel();
  const { createClusterWorkflow, clusterValues, setClusterValues } = useCluster();
  const { openDrawerWithStep } = useDrawer();

  useEffect(() => {
    formData.set("step_number", "1");
    formData.set("workflow_total_steps", "3");
    formData.set("trigger_workflow", "true");
    formData.set("name", values.name);
    formData.set("ingress_url", values.ingress_url);
    formData.set("icon", values.icon);
  }, [values]);

  return (
    <BudForm
      data={{
        icon: "😍",
        ...clusterValues,
      }}
      disableNext={!isValidClusterName(values?.name) || !values.ingress_url || !isValidUrl(values.ingress_url) || !clusterValues.configuration_file}
      onNext={async (values) => {
        // add to form data
        const result = await createClusterWorkflow(formData);
        if (result) {
          await getWorkflow(result.workflow_id);
          openDrawerWithStep("create-cluster-status");
        } else {
          errorToast("Error creating cluster");
        }
      }}
      onBack={
        ()=> openDrawerWithStep("add-cluster-select-source")
      }
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Add Cluster"
            description="Start adding the cluster by entering the details "
          />
          <DrawerCard classNames="pb-0">
            <div className="pt-[.87rem]">
              <ProjectNameInput
                placeholder="Enter Cluster Name"
                onChangeName={(name) => setClusterValues({ ...clusterValues, name })}
                onChangeIcon={(icon) => setClusterValues({ ...clusterValues, icon })}
                isEdit={true}
              />

              <div
                className="height-26"
              />
              <TextInput
                name="ingress_url"
                label="Ingress URL"
                placeholder="Type Ingress URL"
                infoText="Enter the Ingress URL"
                rules={[
                  { required: true, message: "Please enter Ingress URL" },
                  { pattern: new RegExp(/^(http|https):\/\/[^ "]+$/), message: "Please enter a valid URL" }
                ]}
                ClassNames="mt-[.1rem] mb-[0rem]"
                InputClasses="py-[.5rem]"
                formItemClassnames="mb-[1rem]"
                onChange={(value) => { setClusterValues({ ...clusterValues, ingress_url: value }) }}
              />
              <div className="mb-[1.7rem]">
                <Text_14_400_EEEEEE className="p-0 pt-[.3rem] m-0">
                  Configuration
                </Text_14_400_EEEEEE>
                <Text_12_400_757575 className="pt-[.35rem] leading-[1.05rem]">
                  Configuration description
                </Text_12_400_757575>
              </div>
              {formData.get("configuration_file") ?
                <div className="flex justify-start">
                  {clusterValues?.configuration_file && (
                    <Tags
                      name={clusterValues?.configuration_file?.name}
                      color="#D1B854"
                      closable
                      onClose={() => {
                        formData.delete("configuration_file");
                        setFormData(formData);
                        setClusterValues({
                          ...clusterValues,
                          configuration_file: null,
                        });
                      }}
                      classNames="flex"
                    />
                  )}
                </div>
                :
                <FileInput
                  name="configuration_file"
                  acceptedFileTypes={['.yaml, .yml']}
                  label="Upload File"
                  placeholder=""
                  infoText="Upload the configuration file"
                  required
                  text={<div className="flex justify-center items-center w-[100%]">
                    <Text_12_400_B3B3B3>Drag & Drop or </Text_12_400_B3B3B3>&nbsp;
                    <Text_12_600_EEEEEE>Choose file</Text_12_600_EEEEEE>&nbsp;
                    <Text_12_400_B3B3B3> to upload</Text_12_400_B3B3B3>

                  </div>}
                  hint={<>
                    <Text_10_400_757575>Supported formats : YAML, YML</Text_10_400_757575>
                  </>}
                  rules={[{ required: true, message: "Please upload a file" }]}
                  onChange={(value) => {
                    setClusterValues({
                      ...clusterValues,
                      configuration_file: value,
                    });
                    setFormData((prev) => {
                      prev.set("configuration_file", value);
                      return prev;
                    });
                  }}
                />}
            </div>
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
