
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { PaperPublished, useModels } from "src/hooks/useModels";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { successToast } from "@/components/toast";
import { axiosInstance } from "src/pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";
import { useProjects } from "src/hooks/useProjects";





export default function EditProject() {
  const { values } = useContext(BudFormContext);
  const { openDrawer } = useDrawer();
  const { selectedProject } = useProjects();


  return (
    <BudForm
      backText="Back"
      nextText="Save"
      disableNext={!values.name || !values.description}
      onBack={() => openDrawer("view-model")}
      onNext={async () => {

      }}
      data={selectedProject}
    >
     <div></div>
    </BudForm>
  );
}
