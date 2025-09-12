import React, { useContext, useState } from "react";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useProjects } from "@/hooks/useProjects";
import { useDrawer } from "@/hooks/useDrawer";
import { useRouter } from "next/navigation";
import {
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_14_400_EEEEEE,
} from "@/components/ui/text";
import { Icon } from "@iconify/react";
import AlertIcons from "@/flows/components/AlertIcons";

export default function DeleteProject() {
  const { closeDrawer } = useDrawer();
  const { globalSelectedProject, deleteProject, getGlobalProjects } =
    useProjects();
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const projectName = globalSelectedProject?.project?.name || "";
  const projectId = globalSelectedProject?.project?.id;

  const handleDelete = async () => {
    if (!projectId) {
      console.error("No project ID found");
      return;
    }

    try {
      setLoading(true);
      await deleteProject(projectId, null);
      // Refresh the project list - this will fetch the first page
      await getGlobalProjects(1, 10);
      closeDrawer();
      // Only navigate if not already on projects page
      if (!window.location.pathname.includes("/projects")) {
        router.push("/projects");
      }
    } catch (error) {
      console.error("Error deleting project:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <BudForm
      backText="Cancel"
      nextText="Delete Project"
      disableNext={false}
      onBack={() => closeDrawer()}
      onNext={handleDelete}
      data={{}}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Delete Project"
            description={`You're about to delete the project "${projectName}"`}
          />

          <DrawerCard>
            <div className="flex flex-col gap-4">
              {/* Warning Icon and Message */}
              <div className="flex items-start gap-3">
                <div className="mt-1">
                  <AlertIcons type="warining" />
                </div>
                <div className="flex flex-col gap-2">
                  <Text_14_400_EEEEEE className="font-medium">
                    This action cannot be undone
                  </Text_14_400_EEEEEE>
                  <Text_12_400_B3B3B3>
                    Once you delete this project, all associated data including:
                  </Text_12_400_B3B3B3>
                  <ul className="list-disc list-inside ml-2">
                    <li className="text-[#B3B3B3] text-xs">
                      All project configurations
                    </li>
                    <li className="text-[#B3B3B3] text-xs">
                      API keys and credentials
                    </li>
                    <li className="text-[#B3B3B3] text-xs">
                      Deployment history
                    </li>
                    <li className="text-[#B3B3B3] text-xs">
                      Team member associations
                    </li>
                  </ul>
                  <Text_12_400_B3B3B3>
                    will be permanently removed and cannot be recovered.
                  </Text_12_400_B3B3B3>
                </div>
              </div>

              {/* Project Info */}
              <div className="mt-6 p-4 bg-[#1F1F1F] rounded-lg">
                <div className="flex items-center gap-3">
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center text-xl"
                    style={{
                      backgroundColor:
                        globalSelectedProject?.profile_colors?.[0] || "#965CDE",
                    }}
                  >
                    {globalSelectedProject?.project?.icon || "📁"}
                  </div>
                  <div>
                    <Text_14_400_EEEEEE className="font-medium">
                      {projectName}
                    </Text_14_400_EEEEEE>
                    <Text_12_400_B3B3B3>
                      {globalSelectedProject?.project?.description ||
                        "No description"}
                    </Text_12_400_B3B3B3>
                  </div>
                </div>
              </div>

              {/* Confirmation Text */}
              <div className="mt-4 p-3 bg-[#2A1515] border border-[#5C2020] rounded-lg">
                <Text_12_400_EEEEEE className="text-[#FF5E5E]">
                  ⚠️ Are you absolutely sure you want to delete this project?
                </Text_12_400_EEEEEE>
              </div>
            </div>
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
