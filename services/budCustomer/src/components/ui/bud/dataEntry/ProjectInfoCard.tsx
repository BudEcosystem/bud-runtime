import React, { } from "react";

import { getChromeColor } from "./TagsInputData";
import { useProjects } from "@/hooks/useProjects";
import TagsList from "@/flows/components/TagsList";


function ProjectInfoCard() {
  const { selectedProject } = useProjects();

  return (
    <div className="px-[1.4rem] py-[1.4rem]">
      <div className="flex justify-start items-center">
        <div className="w-[2.25rem] h-[2.25rem] rounded-[4px] bg-[#35341B] flex justify-center items-center mr-[1rem] text-[1.5rem]">
          {selectedProject?.icon}
        </div>
        <div className="text-[#EEEEEE] text-[1.125rem] leadign-[100%]">
          {selectedProject?.name || "- "}
        </div>
      </div>
      <div className="flex items-center justify-start gap-[.5rem] mt-[1.4rem] flex-wrap	">
        <TagsList data={selectedProject?.tags} />
      </div>
    </div>
  );
};

export default ProjectInfoCard;
