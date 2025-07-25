import React from "react";
import { Checkbox, Popover } from "antd";
import { Text_14_400_EEEEEE, Text_12_400_757575, Text_10_400_EEEEEE } from "@/components/ui/text";
import Tags from "./DrawerTags";


export interface Evaluation {
    id: string;
    name: string;
    description?: string;
    category?: string;
    tags?: string[];
    metrics?: {
        accuracy?: number;
        latency?: number;
        throughput?: number;
    };
}


export function EvaluationCard({
    data,
    selected,
    handleClick,
    hideSelection
}: {
    data: Evaluation;
    selected?: boolean;
    handleClick?: () => void;
    hideSelection?: boolean;
}) {
    const [hover, setHover] = React.useState(false);
    const [showMore, setShowMore] = React.useState(false);
    const maxTags = 2;

    return (
        <div
            onMouseEnter={() => setHover(true)}
            onClick={handleClick}
            onMouseLeave={() => setHover(false)}
            className="py-[1rem] hover:bg-[#FFFFFF03] cursor-pointer hover:shadow-lg px-[1.4rem] border-b-[0.5px] border-t-[0.5px] border-t-[transparent] border-b-[#1F1F1F] hover:border-t-[.5px] hover:border-[#757575] flex-row flex border-box"
        >
            <div className="flex justify-between items-start w-full">
                <div className=""
                    style={{
                        width: hideSelection ? '100%' : '93%'
                    }}
                >
                    <div className="flex items-center justify-between">
                        <div className="flex items-center justify-start">
                            <Text_14_400_EEEEEE className="truncate overflow-hidden whitespace-nowrap leading-[150%]">{data.name}</Text_14_400_EEEEEE>
                        </div>
                        {data.tags && data.tags.length > 0 && (
                            <div className="flex items-center justify-start gap-[.5rem] mt-[.55rem]">
                                {data.tags.slice(0, maxTags).map((tag, idx) => (
                                    <Tags key={idx} name={tag} color="#965CDE" classNames="py-[.26rem] px-[.4rem]" />
                                ))}
                                {data.tags.length > maxTags && (
                                    <Popover
                                        arrow={false}
                                        showArrow={false}
                                        content={
                                            <div className="flex flex-row flex-wrap gap-[.4rem] border-[#1F1F1F] border rounded-[6px] bg-[#1F1F1F] p-3 max-w-[350px]">
                                                {data.tags.slice(maxTags).map((tag, idx) => (
                                                    <Tags key={idx + maxTags} name={tag} color="#965CDE" classNames="py-[.26rem] px-[.4rem]" />
                                                ))}
                                            </div>
                                        }
                                    >
                                        <div
                                            onMouseEnter={() => setShowMore(true)}
                                            onMouseLeave={() => setShowMore(false)}
                                            className="text-[#EEEEEE] hover:text-[white] text-[0.625rem] font-[400] cursor-pointer">
                                            {showMore ? 'Show less' : `+${data.tags.length - maxTags} more`}
                                        </div>
                                    </Popover>
                                )}
                            </div>
                        )}
                    </div>

                    {data.description && (
                        <div className="flex items-center justify-start mt-[.35rem]">
                            <Text_12_400_757575 className="line-clamp-1">{data.description}</Text_12_400_757575>
                        </div>
                    )}

                </div>

                <div className="flex justify-end items-center w-[1rem] ">
                    {(hover || selected) && !hideSelection && (
                        <Checkbox checked={selected} className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem] mt-[.5rem]" />
                    )}
                </div>

            </div>
        </div>
    );
}

export default function EvaluationList({
    evaluations,
    handleEvaluationSelection,
    selectedEvaluation,
    hideSelection
}: {
    evaluations: Evaluation[];
    handleEvaluationSelection: (evaluation: Evaluation) => void;
    selectedEvaluation: Evaluation | null;
    hideSelection?: boolean;
}) {
    return evaluations?.map((evaluation) => (
        <EvaluationCard
            key={evaluation.id}
            data={evaluation}
            hideSelection={hideSelection}
            selected={evaluation.id === selectedEvaluation?.id}
            handleClick={() => handleEvaluationSelection(evaluation)}
        />
    ))
}