import React from "react";
import { Table } from "antd";
import { ColumnsType } from "antd/es/table";
import { Text_12_400_EEEEEE } from "@/components/ui/text";
import ProjectTags from "src/flows/components/ProjectTags";

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
            title: "Deployment Name",
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
            render: (traits: string[]) => (
                <div className="flex flex-wrap gap-1">
                    {traits && traits.length > 0 ? (
                        traits.map((trait, idx) => (
                            <ProjectTags
                                key={idx}
                                name={trait}
                                color="#965CDE"
                                textClass="text-[.65rem] py-[.15rem]"
                                tagClass="py-[0rem]"
                            />
                        ))
                    ) : (
                        <Text_12_400_EEEEEE>-</Text_12_400_EEEEEE>
                    )}
                </div>
            ),
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
                return <Text_12_400_EEEEEE>{formattedDate}</Text_12_400_EEEEEE>;
            },
            sorter: (a, b) =>
                new Date(a.last_run).getTime() - new Date(b.last_run).getTime(),
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
