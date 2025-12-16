import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Image, Input, Table } from "antd";
import type { TableProps } from "antd";
import { useRouter as useRouter } from "next/router";
import { useDrawer } from "src/hooks/useDrawer";
import { useProjects } from "src/hooks/useProjects";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import {
  Text_12_400_757575,
  Text_12_600_EEEEEE,
} from "@/components/ui/text";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import Tags from "src/flows/components/DrawerTags";
import NoDataFount from "@/components/ui/noDataFount";
import ComingSoon from "@/components/ui/comingSoon";
import { ExperimentData, useEvaluations } from "@/hooks/useEvaluations";
import { getDatasetNamesFromTraits, getDisplayText } from "@/lib/utils";
import { TruncatedTextCell } from "@/components/ui/TruncatedTextCell";
import { errorToast, successToast } from "@/components/toast";
import { tempApiBaseUrl } from "@/components/environment";
import { axiosInstance } from "src/pages/api/requests";

type ColumnsType<T extends object> = TableProps<T>["columns"];
type TablePagination<T extends object> = NonNullable<
  Exclude<TableProps<T>["pagination"], boolean>
>;
type TablePaginationPosition<T extends object> = NonNullable<
  TablePagination<T>["position"]
>[number];

interface DataType {
  type: string;
  dataset: string;
  result: string;
}

function SortIcon({ sortOrder }: { sortOrder: string }) {
  return sortOrder ? (
    sortOrder === "descend" ? (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="12"
        height="13"
        viewBox="0 0 12 13"
        fill="none"
      >
        <path
          fillRule="evenodd"
          clipRule="evenodd"
          d="M6.00078 2.10938C6.27692 2.10938 6.50078 2.33324 6.50078 2.60938L6.50078 9.40223L8.84723 7.05578C9.04249 6.86052 9.35907 6.86052 9.55433 7.05578C9.7496 7.25104 9.7496 7.56763 9.55433 7.76289L6.35433 10.9629C6.15907 11.1582 5.84249 11.1582 5.64723 10.9629L2.44723 7.76289C2.25197 7.56763 2.25197 7.25104 2.44723 7.05578C2.64249 6.86052 2.95907 6.86052 3.15433 7.05578L5.50078 9.40223L5.50078 2.60938C5.50078 2.33324 5.72464 2.10938 6.00078 2.10938Z"
          fill="#B3B3B3"
        />
      </svg>
    ) : (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="12"
        height="13"
        viewBox="0 0 12 13"
        fill="none"
      >
        <path
          fillRule="evenodd"
          clipRule="evenodd"
          d="M6.00078 10.8906C6.27692 10.8906 6.50078 10.6668 6.50078 10.3906L6.50078 3.59773L8.84723 5.94418C9.04249 6.13944 9.35907 6.13944 9.55433 5.94418C9.7496 5.74892 9.7496 5.43233 9.55433 5.23707L6.35433 2.03707C6.15907 1.84181 5.84249 1.84181 5.64723 2.03707L2.44723 5.23707C2.25197 5.43233 2.25197 5.74892 2.44723 5.94418C2.64249 6.13944 2.95907 6.13944 3.15433 5.94418L5.50078 3.59773L5.50078 10.3906C5.50078 10.6668 5.72464 10.8906 6.00078 10.8906Z"
          fill="#B3B3B3"
        />
      </svg>
    )
  ) : null;
}

const data: DataType[] = [
  {
    type: "FaithDial",
    dataset: "lMMLU",
    result: "13.2",
  },
  {
    type: "True-False",
    dataset: "MMLU",
    result: "65.1",
  },
  {
    type: "QA",
    dataset: "MMLU",
    result: "46.9",
  },
  {
    type: "Summarisation",
    dataset: "MMLU",
    result: "78.4",
  },
  {
    type: "Dialogue",
    dataset: "MMLU",
    result: "60.8",
  },
];

const applyFilter = () => {};

function ModelEvalTable() {
  const { openDrawerWithStep } = useDrawer();
  const { getProject } = useProjects();
  const [showSearch, setShowSearch] = useState(false);
  const [searchValue, setSearchValue] = useState("");
  const router = useRouter();
  const { projectId, deploymentId } = router.query; // Access the dynamic part of the route

  const {
    experimentEvaluations,
    experimentEvalTotal,
    loading,
    getEvaluationsData,
  } = useEvaluations();
  const [orderBy, setOrderBy] = useState<string>("created_at");
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);
  const [debouncedSearchValue, setDebouncedSearchValue] = useState("");
  const [order, setOrder] = useState<"-" | "">("");

  const columns: ColumnsType<ExperimentData> = [
    {
      title: "Traits",
      dataIndex: "traits",
      key: "traits",
      // width: 160,
      ellipsis: true,
      render: (traits) => {
        const displayText = getDisplayText(traits, "name", "name");
        return <TruncatedTextCell text={displayText} />;
      },
    },
    {
      title: "Dataset",
      dataIndex: "traits",
      key: "traits",
      // width: 160,
      ellipsis: true,
      render: (traits) => {
        const displayText = getDatasetNamesFromTraits(traits, 1);
        return <TruncatedTextCell text={displayText} />;
      },
    },
    {
      title: "Score",
      dataIndex: "scores",
      key: "scores",
      // width: 160,
      ellipsis: true,
      render: (scores) => {
         return <TruncatedTextCell text={scores?.overall_accuracy || "-"} />;
      },
    },
  ];
  // Table data
  const tableData = useMemo(() => {
    console.log("Experiment Evaluations:", experimentEvaluations);
    if (!experimentEvaluations || !Array.isArray(experimentEvaluations)) {
      return [];
    }
    return experimentEvaluations;
  }, [experimentEvaluations]);

  useEffect(() => {
    getProject(projectId as string);
    // openDrawerWithStep("use-model");
  }, [projectId]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchValue(searchValue);
      setCurrentPage(1); // Reset to first page when search changes
    }, 300);

    return () => clearTimeout(timer);
  }, [searchValue]);

  const fetchExperiments = useCallback(async () => {
    if (typeof deploymentId !== 'string') return;

    try {
      const payload = {
        page: currentPage,
        page_size: pageSize,
        search: debouncedSearchValue || undefined,
        // order: order || undefined,
        // orderBy: orderBy || undefined,
        endpoint_id: deploymentId as string,
        searchName: false
        // experiment_status: "completed",
      };

      await getEvaluationsData(payload);
    } catch (error) {
      console.error("Failed to fetch experiments for model:", error);
    }
  }, [currentPage, pageSize, debouncedSearchValue, order, orderBy, deploymentId, getEvaluationsData]);

  // Fetch data when dependencies change
  useEffect(() => {
    fetchExperiments();
  }, [fetchExperiments]);

  // Handle "Run Another Evaluation" button click
  const handleRunEvaluation = useCallback(() => {
    // Guard: Ensure deploymentId is a valid string before proceeding
    if (typeof deploymentId !== 'string') {
      errorToast("Cannot run evaluation without a valid deployment ID.");
      return;
    }
    // Open the drawer with:
    // - showExperimentSelect: true - to display experiment dropdown
    // - endpointId: deploymentId - to skip the "Select Model" step since we already have the endpoint
    openDrawerWithStep("new-evaluation", {
      showExperimentSelect: true,
      endpointId: deploymentId,
    });
  }, [openDrawerWithStep, deploymentId]);

  // Handle "Export" button click - exports evaluations as CSV
  const handleExport = useCallback(async () => {
    if (typeof deploymentId !== 'string') {
      errorToast("Cannot export without a valid deployment ID.");
      return;
    }

    try {
      const payload = {
        page: currentPage,
        page_size: pageSize,
        search: debouncedSearchValue || undefined,
        endpoint_id: deploymentId,
        searchName: false,
        export_format: 'csv',
      };

      const response = await axiosInstance.get(
        `${tempApiBaseUrl}/experiments/evaluations/all`,
        {
          params: payload,
          responseType: 'blob',
        }
      );

      // Create a blob URL and trigger download
      const blob = new Blob([response.data], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `evaluations_export_${new Date().toISOString().split('T')[0]}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      successToast("Evaluations exported successfully");
    } catch (error) {
      console.error("Failed to export evaluations:", error);
      errorToast("Failed to export evaluations");
    }
  }, [currentPage, pageSize, debouncedSearchValue, deploymentId]);

  return (
    <div className="relative CommonCustomPagination">
      {/* <ComingSoon shrink={true} scaleValue={0.9} comingYpos="-15vh" /> */}
      <Table<ExperimentData>
        columns={columns}
        dataSource={tableData}
        pagination={{
          className: "small-pagination",
          current: currentPage,
          pageSize: pageSize,
          total: experimentEvalTotal || 0,
          onChange: (page, size) => {
            setCurrentPage(page);
            setPageSize(size);
          },
          showSizeChanger: true,
          pageSizeOptions: ["5", "10", "20", "50"],
        }}
        bordered={false}
        footer={null}
        virtual
        onRow={(record, rowIndex) => {
          return {
            onClick: async (event) => {
              // openDrawerWithStep("worker-details")
            },
          };
        }}
        showSorterTooltip={false}
        title={() => (
          <div className="flex justify-between items-center px-[0.75rem] py-[1rem]">
            <div className="flex justify-start items-center gap-[.4rem]">
              {/* <Text_12_400_757575>Modal evaluations summary</Text_12_400_757575> */}
            </div>
            <div className="flex items-center justify-end gap-x-[.5rem]">
              <SearchHeaderInput placeholder="Search by traits, dataset" searchValue={searchValue} setSearchValue={setSearchValue} />

              <PrimaryButton
                onClick={handleRunEvaluation}
                text="Run Another Evaluation"
              ></PrimaryButton>
              <PrimaryButton onClick={handleExport}>
                <div className="flex items-center justify-center">
                  <div className="w-[.75rem] mr-[.25rem]">
                    <Image
                      preview={false}
                      src="/images/drawer/export.png"
                      alt="info"
                      style={{ width: ".75rem", height: ".75rem" }}
                    />
                  </div>
                  <Text_12_600_EEEEEE className="flex items-center justify-center">
                    Export
                  </Text_12_600_EEEEEE>
                </div>
              </PrimaryButton>
            </div>
          </div>
        )}
        locale={{
          emptyText: (
            <NoDataFount classNames="h-[20vh]" textMessage={`No evaluations`} />
          ),
        }}
      />
    </div>
  );
}

export default ModelEvalTable;
