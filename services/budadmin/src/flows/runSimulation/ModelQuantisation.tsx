import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { use, useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import TextInput from "src/flows/components/TextInput";
import TagsInput from "@/components/ui/bud/dataEntry/TagsInput";
import { axiosInstance } from "src/pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";
import {
  ModelNameInput,
  NameIconInput,
} from "@/components/ui/bud/dataEntry/ProjectNameInput";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useDeployModel } from "src/stores/useDeployModel";
import { isValidModelName } from "@/lib/utils";
import CustomSelect from "../components/CustomSelect";

export default function ModelQuantisation() {
  const { openDrawerWithStep } = useDrawer();
  const {
    currentWorkflow,
    updateModelDetailsLocal,
    updateCredentialsLocal,
    localModelDetails,
    deleteWorkflow,
  } = useDeployModel();
  const { values, form } = useContext(BudFormContext);

  const statusOptions = [
    {
      value: "value 1",
      label: "value 1",
    },
    {
      value: "value 2",
      label: "value 2",
    },
  ];

  return (
    <BudForm
      data={localModelDetails}
      onBack={async () => {
        openDrawerWithStep("select-model-for-evaluation");
      }}
      onNext={async () => {
        openDrawerWithStep("select-hardware");
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title={"Model Quantisation"}
            description="Description for Model Quantisation"
          />
          <DrawerCard classNames="">
            <CustomSelect
              name="Status"
              label="Status"
              info="select Status"
              placeholder="Select Status"
              selectOptions={statusOptions}
              value={""}
              onChange={(value) => {
                null;
              }}
              InputClasses="py-[0rem] "
            />
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
