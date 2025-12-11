import React, { useEffect, useState, useCallback, useMemo } from "react";
import { notification, Table, Popover } from "antd";
import { ColumnsType } from "antd/es/table";
import { Model } from "src/hooks/useModels";
import { useRouter } from "next/router";
import { Text_12_400_EEEEEE, Text_16_600_FFFFFF } from "../../text";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import NoDataFount from "../../noDataFount";
import useHandleRouteChange from "@/lib/useHandleRouteChange";
import { useEvaluations, ExperimentData, GetExperimentsPayload } from "src/hooks/useEvaluations";

// Constants
const TEXT_TRUNCATION_LENGTH = 25;

interface EvaluationResultsTableProps {
  model?: Model;
}

// Helper component for rendering truncated text with popover
function TruncatedTextCell({ text }: { text: string }) {
  if (!text || text === "-") {
    return <Text_12_400_EEEEEE>-</Text_12_400_EEEEEE>;
  }

  const needsTruncation = text.length > TEXT_TRUNCATION_LENGTH;
  const truncatedText = needsTruncation
    ? text.substring(0, TEXT_TRUNCATION_LENGTH) + "..."
    : text;

  if (needsTruncation) {
    return (
      <Popover
        content={
          <div className="max-w-[300px] break-words p-[.8rem]">
            <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>
          </div>
        }
        placement="top"
      >
        <div
          className="cursor-pointer"
          style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
        >
          <Text_12_400_EEEEEE>{truncatedText}</Text_12_400_EEEEEE>
        </div>
      </Popover>
    );
  }

  return (
    <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
      <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>
    </div>
  );
}

// Helper function to extract display text from models/traits data
function getDisplayText(
  data: unknown,
  priorityKey: string = "name",
  fallbackKey: string = "name"
): string {
  if (!data) return "-";

  if (typeof data === "string") {
    return data || "-";
  }

  if (Array.isArray(data)) {
    if (data.length === 0) return "-";
    const texts = data
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          return item[priorityKey] || item[fallbackKey] || null;
        }
        return null;
      })
      .filter(Boolean);
    return texts.length > 0 ? texts.join(", ") : "-";
  }

  if (typeof data === "object") {
    const obj = data as Record<string, unknown>;
    const value = obj[priorityKey] || obj[fallbackKey];
    if (typeof value === "string" && value) {
      return value;
    }
    return "-";
  }

  return "-";
}

function EvaluationResultsTable({ model }: EvaluationResultsTableProps) {
  const router = useRouter();

  // State
  const [searchValue, setSearchValue] = useState("");
  const [debouncedSearchValue, setDebouncedSearchValue] = useState("");
  const [order, setOrder] = useState<"-" | "">("");
  const [orderBy, setOrderBy] = useState<string>("created_at");
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);

  // Use Zustand store
  const {
    experimentsList,
    experimentsListTotal,
    loading,
    getExperiments,
  } = useEvaluations();

  useHandleRouteChange(() => {
    notification.destroy();
  });

  // Debounced search effect - updates debouncedSearchValue and resets page together
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchValue(searchValue);
      setCurrentPage(1); // Reset to first page when search changes
    }, 300);

    return () => clearTimeout(timer);
  }, [searchValue]);

  // Fetch experiments filtered by model_id
  const fetchExperiments = useCallback(async () => {
    if (!model?.id) return;

    try {
      const payload: GetExperimentsPayload = {
        page: currentPage,
        limit: pageSize,
        search: debouncedSearchValue || undefined,
        order: order || undefined,
        orderBy: orderBy || undefined,
        model_id: model.id,
        experiment_status: "completed",
      };

      await getExperiments(payload);
    } catch (error) {
      console.error("Failed to fetch experiments for model:", error);
    }
  }, [currentPage, pageSize, debouncedSearchValue, order, orderBy, model?.id, getExperiments]);

  // Fetch data when dependencies change
  useEffect(() => {
    fetchExperiments();
  }, [fetchExperiments]);

  // Table data
  const tableData = useMemo(() => {
    if (!experimentsList || !Array.isArray(experimentsList)) {
      return [];
    }
    return experimentsList;
  }, [experimentsList]);

  // Table columns
  const columns: ColumnsType<ExperimentData> = [
    {
      title: "Deployment Name",
      dataIndex: "models",
      key: "models",
      // width: 180,
      ellipsis: true,
      render: (models) => {
        const displayText = getDisplayText(models, "deployment_name", "name");
        return <TruncatedTextCell text={displayText} />;
      },
    },
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
      dataIndex: "dataset_name",
      key: "dataset_name",
      // width: 160,
      ellipsis: true,
      render: (datasetName) => {
        return <TruncatedTextCell text={datasetName || "-"} />;
      },
    },
  ];

  const handleTableChange = (_pagination: any, _filters: any, sorter: any) => {
    if (sorter.field) {
      setOrder(sorter.order === "ascend" ? "" : "-");
      setOrderBy(sorter.field);
    }
  };

  return (
    <div className="pb-[30px] pt-[.4rem]">
      <div className="userTable evalTable relative CommonCustomPagination evaluation-results-table">
        <style jsx global>{`
          .evaluation-results-table .ant-table-placeholder .ant-table-cell {
            text-align: center !important;
            padding: 16px !important;
          }
          .evaluation-results-table .ant-table-placeholder td {
            width: 100% !important;
          }
          .evaluation-results-table .ant-table-tbody .ant-table-placeholder > td {
            text-align: center !important;
          }
          .evaluation-results-table .ant-empty,
          .evaluation-results-table .ant-table-empty .ant-table-tbody > tr > td {
            text-align: center !important;
          }
          .evaluation-results-table .ant-table-placeholder .ant-table-cell > div {
            display: flex;
            justify-content: center;
            align-items: center;
            width: 100%;
          }
        `}</style>
        <Table<ExperimentData>
          columns={columns}
          dataSource={tableData}
          pagination={{
            className: "small-pagination",
            current: currentPage,
            pageSize: pageSize,
            total: experimentsListTotal || 0,
            onChange: (page, size) => {
              setCurrentPage(page);
              setPageSize(size);
            },
            showSizeChanger: true,
            pageSizeOptions: ["5", "10", "20", "50"],
          }}
          loading={loading}
          onChange={handleTableChange}
          onRow={(record) => ({
            onClick: () => router.push(`/home/evaluations/experiments/${record.id}`),
            style: { cursor: "pointer" },
            className: "group",
          })}
          showSorterTooltip={false}
          rowKey="id"
          bordered={false}
          title={() => (
            <div className="flex justify-between items-center px-[0.75rem] py-[1rem] gap-x-[.4rem]">
              <Text_16_600_FFFFFF className="text-[#EEEEEE] whitespace-nowrap">
                Evaluation Results
              </Text_16_600_FFFFFF>
              <div className="flex items-center justify-between gap-x-[.4rem]">
                <SearchHeaderInput
                  placeholder="Search by name"
                  searchValue={searchValue}
                  classNames="flex-1"
                  fullWidth={true}
                  setSearchValue={setSearchValue}
                />
                {/* {hasPermission(PermissionEnum.ModelManage) && (
                  <PrimaryButton
                    onClick={() => {
                      router.push("/home/evaluations/experiments");
                    }}
                  >
                    <div className="flex items-center justify-center">
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
                          d="M5.48129 3.47747L6.12128 2.83745C6.63692 2.32183 7.54131 1.96401 8.44 1.83563C8.8829 1.77236 9.30173 1.76843 9.64357 1.81962C9.99743 1.87261 10.2143 1.9762 10.3156 2.07749C10.4169 2.17877 10.5205 2.39563 10.5735 2.74949C10.6247 3.09131 10.6207 3.51014 10.5575 3.95304C10.4291 4.85174 10.0712 5.75613 9.55559 6.27179L5.99843 9.82895L5.08127 8.91179C4.92506 8.75558 4.67179 8.75558 4.51558 8.91179C4.35937 9.068 4.35937 9.32127 4.51558 9.47748L5.71559 10.6775C5.8718 10.8337 6.12507 10.8337 6.28128 10.6775L6.71902 10.2397L7.65543 11.8004C7.7188 11.906 7.8273 11.9766 7.94956 11.9916C8.07181 12.0067 8.19417 11.9646 8.28127 11.8775L9.88127 10.2775C9.9703 10.1884 10.0122 10.0627 9.99441 9.93806L9.6227 7.33606L10.1213 6.83747C10.8056 6.15309 11.2078 5.05747 11.3494 4.06617C11.4211 3.56407 11.4297 3.06541 11.3647 2.631C11.3014 2.20861 11.16 1.79048 10.8813 1.51179C10.6026 1.2331 10.1844 1.09169 9.76205 1.02844C9.32764 0.963385 8.82897 0.971945 8.32687 1.04367C7.33558 1.18527 6.23995 1.58743 5.55559 2.27177L5.05701 2.77037L2.45501 2.39866C2.33037 2.38085 2.20462 2.42277 2.1156 2.51179L0.515598 4.11179C0.428501 4.19889 0.386388 4.32126 0.401438 4.44351C0.416488 4.56576 0.487022 4.67426 0.592643 4.73763L2.15335 5.67405L1.71561 6.11179C1.64059 6.18681 1.59845 6.28855 1.59845 6.39463C1.59845 6.50072 1.64059 6.60246 1.71561 6.67748L2.91561 7.87748C3.07182 8.03369 3.32509 8.03369 3.4813 7.87748C3.63751 7.72127 3.63751 7.468 3.4813 7.31179L2.56414 6.39464L3.0813 5.87748L5.48129 3.47747ZM8.07784 10.9495L7.30211 9.65664L8.91559 8.04317L9.17416 9.85321L8.07784 10.9495ZM2.73645 5.09096L4.34991 3.47748L2.53986 3.2189L1.44354 4.31522L2.73645 5.09096ZM1.88128 8.67747C2.03749 8.52126 2.03749 8.26799 1.88128 8.11178C1.72507 7.95557 1.47181 7.95557 1.3156 8.11178L0.515598 8.91178C0.359388 9.06799 0.359388 9.32126 0.515598 9.47747C0.671808 9.63368 0.925074 9.63368 1.08128 9.47747L1.88128 8.67747ZM3.0813 9.87749C3.23751 9.72128 3.23752 9.46801 3.08131 9.3118C2.9251 9.15559 2.67183 9.15559 2.51562 9.31179L0.915601 10.9118C0.75939 11.068 0.759387 11.3213 0.915595 11.4775C1.0718 11.6337 1.32507 11.6337 1.48128 11.4775L3.0813 9.87749ZM4.28128 11.0775C4.43749 10.9213 4.43749 10.668 4.28128 10.5118C4.12507 10.3556 3.87181 10.3556 3.7156 10.5118L2.9156 11.3118C2.75939 11.468 2.75939 11.7213 2.9156 11.8775C3.07181 12.0337 3.32507 12.0337 3.48128 11.8775L4.28128 11.0775ZM7.59671 5.79498C8.14847 5.79498 8.59576 5.34769 8.59576 4.79593C8.59576 4.24417 8.14847 3.79688 7.59671 3.79688C7.04495 3.79688 6.59766 4.24417 6.59766 4.79593C6.59766 5.34769 7.04495 5.79498 7.59671 5.79498Z"
                          fill="#EEEEEE"
                        />
                      </svg>
                      <div className="ml-2" />
                      Run Evaluations
                    </div>
                  </PrimaryButton>
                )} */}
              </div>
            </div>
          )}
          locale={{
            emptyText: (
              <NoDataFount
                  classNames="h-[20vh]"
                  textMessage="No experiments found for this model"
                />
            ),
          }}
        />
      </div>
    </div>
  );
}

export default EvaluationResultsTable;
