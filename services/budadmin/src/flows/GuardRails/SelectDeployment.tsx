import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Input, Checkbox, Spin, Popover } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import React, { useState, useEffect, useRef, useCallback } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { errorToast } from "@/components/toast";
import useGuardrails from "src/hooks/useGuardrails";
import {
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_14_400_EEEEEE,
  Text_14_600_FFFFFF,
} from "@/components/ui/text";
import IconRender from "../components/BudIconRender";
import Tags from "../components/DrawerTags";
import { endpointStatusMapping } from "@/lib/colorMapping";
import { AppRequest } from "src/pages/api/requests";
import { tempApiBaseUrl } from "@/components/environment";


interface EndpointItem {
  id?: string;
  endpoint_id?: string;
  name?: string;
  endpoint_name?: string;
  endpoint_url?: string;
  description?: string;
  status?: string;
  model?: {
    icon?: string;
    provider_type?: string;
    [key: string]: any;
  };
}

export default function SelectDeployment() {
  const { openDrawerWithStep, currentFlow } = useDrawer();
  const isCloudFlow = currentFlow === "add-guardrail-cloud";
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedDeployment, setSelectedDeployment] = useState<string>("");
  const [selectedDeploymentData, setSelectedDeploymentData] =
    useState<any>(null);

  // Helper function to get status color
  const getStatusColor = (status: string): string => {
    const statusKey =
      status.charAt(0).toUpperCase() + status.slice(1).toLowerCase();

    // Check for exact match first
    if (endpointStatusMapping[statusKey]) {
      return endpointStatusMapping[statusKey];
    }

    // Check for specific statuses
    if (status.toLowerCase() === "active") {
      return "#479D5F"; // Green for active
    }
    if (status.toLowerCase() === "running") {
      return "#479D5F"; // Green for running
    }
    if (status.toLowerCase() === "deploying") {
      return "#965CDE"; // Purple for deploying
    }
    if (status.toLowerCase() === "failed" || status.toLowerCase() === "error") {
      return "#EC7575"; // Red for failed/error
    }
    if (
      status.toLowerCase() === "stopped" ||
      status.toLowerCase() === "paused"
    ) {
      return "#DE5CD1"; // Pink for stopped/paused
    }
    if (
      status.toLowerCase() === "unhealthy" ||
      status.toLowerCase() === "processing"
    ) {
      return "#D1B854"; // Yellow for unhealthy/processing
    }

    // Default color if no match
    return "#757575"; // Gray as default
  };

  // Infinite scroll pagination states
  const pageSize = 10;
  const [allEndpoints, setAllEndpoints] = useState<EndpointItem[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalRecordCount, setTotalRecordCount] = useState(0);
  const [initialLoading, setInitialLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const sentinelRef = useRef<HTMLDivElement>(null);

  const {
    selectedProject,
    updateWorkflow,
    workflowLoading,
    setSelectedDeployment: setSelectedDeploymentInStore,
  } = useGuardrails();

  // Local fetch that accumulates results
  const fetchEndpoints = useCallback(
    async (page: number, search?: string, append: boolean = false) => {
      const projectId = selectedProject?.project?.id || selectedProject?.id;
      if (!projectId) return;

      if (append) {
        setLoadingMore(true);
      } else {
        setInitialLoading(true);
      }

      try {
        const params: any = {
          page,
          limit: pageSize,
          search: search ? true : false,
          name: search || undefined,
          order_by: "-created_at",
        };
        if (projectId) {
          params.project_id = projectId;
        }

        const response: any = await AppRequest.Get(
          `${tempApiBaseUrl}/endpoints/`,
          {
            params,
            headers: {
              "x-resource-type": "project",
              "x-entity-id": projectId,
            },
          }
        );

        const listData = response?.data;
        if (listData?.endpoints) {
          const newEndpoints = listData.endpoints;
          const totalPages = listData.total_pages || Math.ceil((listData.total_record || 0) / pageSize);

          if (append) {
            setAllEndpoints((prev) => [...prev, ...newEndpoints]);
          } else {
            setAllEndpoints(newEndpoints);
          }

          setTotalRecordCount(listData.total_record || 0);
          setHasMore(page < totalPages);
        }
      } catch (error) {
        console.error("Failed to fetch endpoints:", error);
        if (!append) {
          setAllEndpoints([]);
        }
      } finally {
        if (append) {
          setLoadingMore(false);
        } else {
          setInitialLoading(false);
        }
      }
    },
    [selectedProject]
  );

  // Reset and fetch on search change
  useEffect(() => {
    const timer = setTimeout(() => {
      setCurrentPage(1);
      setHasMore(true);
      fetchEndpoints(1, searchTerm || undefined, false);
    }, 300);

    return () => clearTimeout(timer);
  }, [searchTerm, selectedProject, fetchEndpoints]);

  // Infinite scroll observer
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const [entry] = entries;
        if (entry.isIntersecting && hasMore && !loadingMore && !initialLoading) {
          const nextPage = currentPage + 1;
          setCurrentPage(nextPage);
          fetchEndpoints(nextPage, searchTerm || undefined, true);
        }
      },
      {
        root: null,
        rootMargin: "100px",
        threshold: 0.1,
      }
    );

    const sentinel = sentinelRef.current;
    if (sentinel) {
      observer.observe(sentinel);
    }

    return () => {
      if (sentinel) {
        observer.unobserve(sentinel);
      }
    };
  }, [hasMore, loadingMore, initialLoading, currentPage, searchTerm, fetchEndpoints]);


  const handleBack = () => {
    openDrawerWithStep(isCloudFlow ? "cloud-deployment-types" : "deployment-types");
  };

  const handleNext = async () => {
    if (!selectedDeployment) {
      errorToast("Please select a deployment");
      return;
    }

    try {
      // Backend accumulates data across steps, so only send step-specific fields
      const payload: any = {
        step_number: 6,
        endpoint_ids: [selectedDeployment],
      };

      // Update workflow with step-specific data
      const success = await updateWorkflow(payload);

      // Only navigate to next step if API call was successful
      if (success) {
        // Store the selected deployment in the guardrails store
        setSelectedDeploymentInStore(selectedDeploymentData);
        // Move to probe settings
        openDrawerWithStep(isCloudFlow ? "cloud-probe-settings" : "probe-settings");
      }
      // If not successful, stay on current page (error toast is shown by updateWorkflow)
    } catch (error) {
      console.error("Failed to update workflow:", error);
    }
  };

  const handleDeploymentSelect = (deployment: any, type: string) => {
    const id = deployment.endpoint_id || deployment.id;
    setSelectedDeployment(id);
    setSelectedDeploymentData({ ...deployment, type });
    // Store the deployment in the guardrails store
    setSelectedDeploymentInStore({ ...deployment, type });
  };


  // Render deployment/endpoint item
  const renderDeploymentListItem = (endpoint: EndpointItem) => {
    const description = endpoint.endpoint_url || endpoint.description || "";
    const isLongDescription = description.length > 60;

    return (
      <div
        key={endpoint.endpoint_id || endpoint.id}
        onClick={() => handleDeploymentSelect(endpoint, "deployment")}
        className={`pt-[1.05rem] px-[1.35rem] pb-[.8rem] cursor-pointer hover:shadow-lg border-y-[0.5px] flex-row flex hover:bg-[#FFFFFF08] transition-all ${
          selectedDeployment === (endpoint.endpoint_id || endpoint.id)
            ? "border-y-[#965CDE] bg-[#965CDE10]"
            : "border-y-[#1F1F1F] hover:border-[#757575]"
        }`}
      >
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-[1rem]">
            {/* Deployment Icon - Use IconRender if model is available */}
            {endpoint.model ? (
              <IconRender
                icon={endpoint.model?.icon}
                size={43}
                imageSize={24}
                type={endpoint.model?.provider_type}
                model={endpoint.model}
              />
            ) : (
              <div className="bg-[#1F1F1F] rounded-[0.515625rem] w-[2.6875rem] h-[2.6875rem] flex justify-center items-center shrink-0">
                <span className="text-[1.2rem]">🚀</span>
              </div>
            )}

            {/* Deployment Details */}
            <div className="flex flex-col">
              <Text_14_400_EEEEEE className="mb-[0.25rem]">
                {endpoint.name || endpoint.endpoint_name}
              </Text_14_400_EEEEEE>
              {description && (
                <div className="flex items-center gap-[0.5rem]">
                  <Text_12_400_757575 className="line-clamp-1">
                    {description}
                  </Text_12_400_757575>
                  {isLongDescription && (
                    <Popover
                      content={
                        <div className="max-w-[400px]">
                          <Text_12_400_757575>{description}</Text_12_400_757575>
                        </div>
                      }
                      trigger="hover"
                      placement="top"
                      overlayClassName="[&_.ant-popover-inner]:!bg-[#2A2A2A] [&_.ant-popover-arrow]:!hidden"
                    >
                      <span
                        className="text-[#965CDE] text-[12px] cursor-pointer hover:text-[#a876e6] whitespace-nowrap"
                        onClick={(e) => e.stopPropagation()}
                      >
                        see more
                      </span>
                    </Popover>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Selection Indicator */}
          <div className="flex items-center gap-[0.75rem]">
            {endpoint.status && (
              <Tags
                name={
                  endpoint.status.charAt(0).toUpperCase() +
                  endpoint.status.slice(1).toLowerCase()
                }
                color={getStatusColor(endpoint.status)}
                textClass="!text-[0.75rem] px-[0.25rem]"
              />
            )}
            <Checkbox
              checked={
                selectedDeployment === (endpoint.endpoint_id || endpoint.id)
              }
              className="AntCheckbox pointer-events-none"
            />
          </div>
        </div>
      </div>
    );
  };


  return (
    <BudForm
      data={{}}
      onBack={handleBack}
      onNext={handleNext}
      backText="Back"
      nextText="Next"
      disableNext={!selectedDeployment || workflowLoading}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Select Deployment"
            description="Select from the available deployment to which you would like to add the Guardrail to."
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem] text-[#B3B3B3]"
          />

          <div className="pb-[1.35rem]">
            {/* Search Bar */}
            <div className="mb-[1.5rem] px-[1.35rem]">
              <Input
                placeholder="Search"
                prefix={<SearchOutlined className="text-[#757575]" />}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="bg-transparent text-[#EEEEEE] border-[#757575] hover:border-[#EEEEEE] focus:border-[#EEEEEE]"
                style={{
                  backgroundColor: "transparent",
                  color: "#EEEEEE",
                }}
              />
            </div>

            {/* Deployments Section */}
            <div className="mb-[1rem]">
              <div className="flex items-center gap-[0.5rem] px-[1.35rem] mb-[1rem]">
                <Text_14_600_FFFFFF>Deployments</Text_14_600_FFFFFF>
                <Text_12_400_757575>
                  ({totalRecordCount || 0})
                </Text_12_400_757575>
              </div>
                {initialLoading ? (
                  <div className="flex justify-center py-[2rem]">
                    <Spin size="large" />
                  </div>
                ) : (
                  <>
                    {allEndpoints.length > 0 ? (
                      <>
                        <div className="space-y-0">
                          {allEndpoints.map((endpoint) =>
                            renderDeploymentListItem(endpoint),
                          )}
                        </div>
                        {/* Infinite scroll sentinel */}
                        <div
                          ref={sentinelRef}
                          className="flex justify-center items-center py-4"
                        >
                          {loadingMore && <Spin size="default" />}
                          {!hasMore && allEndpoints.length > 0 && (
                            <Text_12_400_B3B3B3>No more deployments to load</Text_12_400_B3B3B3>
                          )}
                        </div>
                      </>
                    ) : (
                      <div className="text-center py-[2rem]">
                        <Text_12_400_757575>
                          No deployments found
                        </Text_12_400_757575>
                      </div>
                    )}
                  </>
                )}
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
