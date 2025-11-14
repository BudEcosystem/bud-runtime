import React from "react";
import { Table, Popover } from "antd";
import { ColumnsType } from "antd/es/table";
import { Text_12_400_EEEEEE } from "@/components/ui/text";
import ProjectTags from "src/flows/components/ProjectTags";
import { formatDate } from "@/utils/formatDate";
import { endpointStatusMapping } from "@/lib/colorMapping";
import { capitalize } from "@/lib/utils";

interface CurrentMetricItem {
    evaluation: string;
    dataset: string;
    deployment_name: string;
    score: string;
    score_value: number;
    traits: string[];
    last_run: string;
    status: string;
    run_id: string;
    model_name: string;
}

interface CurrentMetricsTableProps {
    data: CurrentMetricItem[];
}

const CurrentMetricsTable: React.FC<CurrentMetricsTableProps> = ({ data }) => {
    const columns: ColumnsType<CurrentMetricItem> = [
        {
            title: "Evaluation",
            dataIndex: "evaluation",
            key: "evaluation",
            render: (text: string) => (
                <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>
            ),
        },
        {
            title: "Dataset",
            dataIndex: "dataset",
            key: "dataset",
            render: (text: string) => (
                <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>
            ),
        },
        {
            title: "Model Name",
            dataIndex: "model_name",
            key: "model_name",
            render: (text: string) => (
                <Text_12_400_EEEEEE>
                    {text || "Unknown Model"}
                </Text_12_400_EEEEEE>
            ),
        },
        {
            title: "Score",
            dataIndex: "score",
            key: "score",
            render: (text: string) => (
                <Text_12_400_EEEEEE>{text}</Text_12_400_EEEEEE>
            ),
            sorter: (a, b) => a.score_value - b.score_value,
        },
        {
            title: "Traits",
            dataIndex: "traits",
            key: "traits",
            render: (traits: string[]) => {
                if (!traits || traits.length === 0) {
                    return <Text_12_400_EEEEEE>-</Text_12_400_EEEEEE>;
                }

                const visibleTraits = traits.slice(0, 2);
                const remainingTraits = traits.slice(2);
                const hasMore = remainingTraits.length > 0;

                return (
                    <div className="flex flex-wrap gap-1 items-center">
                        {visibleTraits.map((trait, idx) => (
                            <ProjectTags
                                key={idx}
                                name={trait}
                                color="#965CDE"
                                textClass="text-[.65rem] py-[.15rem]"
                                tagClass="py-[0rem]"
                            />
                        ))}
                        {hasMore && (
                            <Popover
                                content={
                                    <div className="flex flex-wrap gap-1 max-w-[300px] p-[0.5rem]">
                                        {traits.map((trait, idx) => (
                                            <ProjectTags
                                                key={idx}
                                                name={trait}
                                                color="#965CDE"
                                                textClass="text-[.65rem] py-[.15rem]"
                                                tagClass="py-[0rem]"
                                            />
                                        ))}
                                    </div>
                                }
                                title={
                                    <span className="text-white font-medium px-[0.5rem]">All Traits</span>
                                }
                                trigger="hover"
                                placement="top"
                                color="#1F1F1F"
                                arrow={true}
                            >
                                <div className="flex items-center justify-center h-[1.2rem] w-[1.2rem] bg-[#965CDE20] rounded-full cursor-pointer hover:bg-[#965CDE30] transition-colors">
                                    <span className="text-[#965CDE] text-[.65rem] font-medium">
                                        +{remainingTraits.length}
                                    </span>
                                </div>
                            </Popover>
                        )}
                    </div>
                );
            },
        },
        {
            title: "Last Run",
            dataIndex: "last_run",
            key: "last_run",
            render: (date: string) => {
                if (!date) return <Text_12_400_EEEEEE>-</Text_12_400_EEEEEE>;
                const formattedDate = new Date(date).toLocaleDateString(
                    "en-US",
                    {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                    },
                );
                return <Text_12_400_EEEEEE>{formatDate(date)}</Text_12_400_EEEEEE>;
            },
            sorter: (a, b) =>
                new Date(a.last_run).getTime() - new Date(b.last_run).getTime(),
        },
        {
            title: "Status",
            dataIndex: "status",
            key: "status",
            render: (status: string) => (
                <ProjectTags
                    name={capitalize(status)}
                    color={
                        endpointStatusMapping[
                            capitalize(status) === "Running"
                                ? capitalize(status) + "-yellow"
                                : capitalize(status)
                        ]
                    }
                    textClass="text-[.75rem] py-[.22rem]"
                    tagClass="py-[0rem]"
                />
            ),
        },
    ];

    return (
        <div className="current-metrics-table eval-explorer-wrapper">
            <style jsx global>{`
                .current-metrics-table .ant-table {
                    background: transparent;
                }
                .current-metrics-table .ant-table-thead > tr > th {
                    background: transparent;
                    border-bottom: 1px solid #1f1f1f;
                    color: #b3b3b3;
                    font-size: 12px;
                    font-weight: 400;
                    padding: 12px 16px;
                }
                .current-metrics-table .ant-table-tbody > tr > td {
                    background: transparent;
                    border-bottom: 1px solid #1f1f1f;
                    padding: 12px 16px;
                }
                .current-metrics-table .ant-table-tbody > tr:hover > td {
                    background: rgba(255, 255, 255, 0.02);
                }
                .current-metrics-table .ant-table-tbody > tr:last-child > td {
                    border-bottom: none;
                }
            `}</style>
            <Table
                columns={columns}
                dataSource={data}
                pagination={false}
                rowKey="run_id"
                size="small"
            />
        </div>
    );
};

export default CurrentMetricsTable;
