
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
import { ModelNameInput, NameIconInput } from "@/components/ui/bud/dataEntry/ProjectNameInput";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useDeployModel } from "src/stores/useDeployModel";
import { isValidModelName } from "@/lib/utils";
import TextAreaInput from "@/components/ui/bud/dataEntry/TextArea";


export default function NewEvaluation() {
  const { openDrawerWithStep } = useDrawer()
  const { currentWorkflow, updateModelDetailsLocal, updateCredentialsLocal, localModelDetails, deleteWorkflow } = useDeployModel();
  const { values, form } = useContext(BudFormContext);



  return (
    <BudForm
      data={localModelDetails}
      onBack={async () => {
        openDrawerWithStep('select-use-case')
      }}

      onNext={async () => {
        openDrawerWithStep('select-model-new-evaluation')
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title={'New Evaluation'}
            description="Description for New Evaluation"
          />
          <DrawerCard classNames="">

            <TextInput
              name="EvaluationName"
              label={'Evaluation Name'}
              placeholder={'Enter evaluation name'}
              rules={[{ required: true, message: 'Please enter evaluation name' }]}
              ClassNames="mt-[.55rem]"
              InputClasses="pt-[.6rem] pb-[.4rem]"
              formItemClassnames="mb-[.45rem]"
              infoText={'Enter Requests count'}
            />
            <TextAreaInput
              name="Description"
              label="Description"
              required
              info="Enter description"
              placeholder="Enter description"
              rules={[{ required: true, message: "Enter description" }]}
            />
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
