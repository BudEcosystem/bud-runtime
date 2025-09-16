import ProjectSuccessCard from "@/components/ui/bud/card/ProjectSuccessCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React from "react";
import { useDrawer } from "src/hooks/useDrawer";

interface Props {
  text: string;
}

export default function CreateProjectSuccess(props: Props) {
  const { closeDrawer } = useDrawer();
  return (
    <BudForm
      data={{}}
      backText="Close"
      onBack={() => {
        closeDrawer();
      }}
    >
      <BudWraperBox center={true}>
        <BudDrawerLayout>
          <ProjectSuccessCard text={props.text} />
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
