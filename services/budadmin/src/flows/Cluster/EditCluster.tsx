import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useContext, useEffect } from "react";
import TextInput from "../components/TextInput";
import { useCluster } from "src/hooks/useCluster";
import { errorToast, successToast } from "@/components/toast";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import ProjectNameInput, {
  NameImageDisplay,
} from "@/components/ui/bud/dataEntry/ProjectNameInput";
import { isValidClusterName, isValidModelName } from "@/lib/utils";

const urlPattern = new RegExp(/^(http|https):\/\/[^ "]+$/);

function EditClusterForm() {
  const { selectedCluster } = useCluster();
  const { form } = useContext(BudFormContext);
  return (
    <BudWraperBox>
      <BudDrawerLayout>
        <DrawerTitleCard
          title="Edit Cluster"
          description="Edit cluster information below"
        />
        <DrawerCard classNames="pb-0">
          <ProjectNameInput
            placeholder="Enter Cluster Name"
            onChangeName={(name) => form.setFieldsValue({ name })}
            onChangeIcon={(icon) => form.setFieldsValue({ icon })}
            isEdit={true}
          />
          <div className="height-26" />
          <TextInput
            name="ingress_url"
            label="Ingress URL"
            placeholder="Type Ingress URL"
            infoText="Ingress URL is the URL that will be used to access the cluster"
            rules={[
              { required: true, message: "Please enter Ingress URL" },
              { pattern: urlPattern, message: "Please enter a valid URL" },
            ]}
            ClassNames="mt-[.4rem]"
            InputClasses="py-[.5rem]"
          />
        </DrawerCard>
      </BudDrawerLayout>
    </BudWraperBox>
  );
}

export default function EditCluster() {
  const { values } = useContext(BudFormContext);
  const { selectedCluster, updateCluster, refresh } = useCluster();

  return (
    <BudForm
      nextText="Save"
      data={{
        ...selectedCluster,
        icon: selectedCluster.icon?.length > 1 ? "😍" : selectedCluster.icon,
      }}
      disableNext={
        !isValidClusterName(values?.name) ||
        !values?.ingress_url ||
        !urlPattern.test(values?.ingress_url)
      }
      onNext={async (values) => {
        const payload = {
          name: values.name,
          icon: values.icon,
          ingress_url: values.ingress_url,
        };
        const result = await updateCluster(selectedCluster.id, payload);
        refresh();
        if (result) {
          successToast("Cluster updated successfully");
        }
      }}
    >
      <EditClusterForm />
    </BudForm>
  );
}
