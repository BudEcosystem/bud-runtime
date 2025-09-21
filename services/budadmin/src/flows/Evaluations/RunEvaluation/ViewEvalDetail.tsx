import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import {
  Text_10_400_FFFFFF,
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_12_400_FFFFFF,
  Text_12_600_EEEEEE,
  Text_14_400_EEEEEE,
  Text_14_600_FFFFFF,
} from "@/components/ui/text";
import React, { useContext, useEffect, useState, useRef } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { Image, Tag } from "antd";
import { useEvaluations } from "src/hooks/useEvaluations";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { ExternalLink, Play } from "lucide-react";
import CustomDropDown from "../../components/CustomDropDown";

interface ExampleItem {
  prompt: string;
  output: string;
  isVideo?: boolean;
  isImage?: boolean;
  videoTime?: string;
}

export default function ViewEvalDetailscopy() {
  const { isExpandedViewOpen } = useContext(BudFormContext);
  const { closeExpandedStep, openDrawerWithStep } = useDrawer();
  const { selectedEvals, getEvaluationDetails, evaluationDetails, loading } =
    useEvaluations();
  const [isExpanded, setIsExpanded] = useState(false);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const descriptionRef = useRef(null);

  // The evaluation details are now fetched in SelectEvaluation before opening the drawer
  // This ensures data is loaded before the drawer opens
  useEffect(() => {
    console.log("evaluationDetails", evaluationDetails);
  }, [evaluationDetails]);

  // Use real data from API or fallback to defaults
  const dataset = evaluationDetails?.dataset || evaluationDetails || {};
  const evaluationData = {
    name: dataset?.name || selectedEvals[0]?.name || "MMLU",
    description:
      dataset?.description ||
      selectedEvals[0]?.description ||
      "Lorem ipsum is simply dummy text of the printing and typesetting industry.",
    author: dataset?.meta_links?.author || "Github Link",
    authorUrl: dataset?.meta_links?.author_url || "#",
    website: dataset?.meta_links?.website || "Website Link",
    websiteUrl: dataset?.meta_links?.website_url || "#",
    paper: dataset?.meta_links?.papers?.join(", ") || "Paper 1, Paper 2",
    traits: dataset?.domains ||
      selectedEvals[0]?.domains || ["Trait", "Domain", "Language", "Modality"],
    language: dataset?.language || [],
    modalities: dataset?.modalities || [],
    task_type: dataset?.task_type || [],
    advantages: dataset?.advantages_disadvantages?.advantages || [
      "InternLM 2.5 offers strong reasoning across the board as well as tool",
      "InternLM 2.5 offers strong reasoning across the board as well as tool use for developers, while sitting at the sweet spot of size for those with 24GB GPUs.",
      "InternLM",
    ],
    disadvantages: dataset?.advantages_disadvantages?.disadvantages || [
      "Delivering a full-list of disadvantages of the evaluation",
      "InternLM 2.5 offers strong reasoning across the board as well as tool use for developers, while sitting at the sweet spot of size for those with 24GB GPUs.",
      "InternLM",
    ],
    examples: dataset?.sample_questions_answers?.samples || [
      {
        prompt:
          "InternLM 2.5 offers strong reasoning across the board as well as tool use for developers, while sitting at the sweet spot of size for those with 24GB GPUs.",
        output:
          "InternLM 2.5 offers strong reasoning across the board as well as tool use for developers, while sitting at the sweet spot of size for those with 24GB GPUs.",
      },
    ],
    estimated_input_tokens: dataset?.estimated_input_tokens || 0,
    estimated_output_tokens: dataset?.estimated_output_tokens || 0,
  };

  const toggleDescription = () => setIsExpanded(!isExpanded);

  useEffect(() => {
    if (descriptionRef.current) {
      const element = descriptionRef.current;
      setIsOverflowing(element.scrollHeight > 50);
    }
  }, [evaluationData.description]);

  const renderExample = (example: ExampleItem, index: number) => (
    <div
      key={index}
      className="rounded-[8px] mt-[.7rem] px-[.9rem] py-[1.1rem] bg-[#FFFFFF08]"
    >
      <div>
        <Text_12_400_EEEEEE>Prompt</Text_12_400_EEEEEE>
        <div className="flex justify-between items-center px-[.9rem] py-[.7rem] border border-[#757575] rounded-[8px] mt-[.4rem]">
          <Text_12_400_B3B3B3 className="leading-[1.05rem]">
            {example.prompt}
          </Text_12_400_B3B3B3>
        </div>
      </div>
      <div className="mt-[1.7rem]">
        <Text_12_400_EEEEEE>Output</Text_12_400_EEEEEE>
        {example.isVideo ? (
          <div className="flex justify-between items-center px-[.9rem] py-[.7rem] border border-[#757575] rounded-[8px] mt-[.4rem]">
            <div className="flex items-center gap-2">
              <Play className="w-4 h-4 text-[#757575]" />
              <Text_12_400_757575>{example.videoTime}</Text_12_400_757575>
            </div>
          </div>
        ) : example.isImage ? (
          <div className="border border-[#757575] rounded-[8px] mt-[.4rem] overflow-hidden">
            <img
              src="/images/evaluations/sample-output.png"
              alt="Output visualization"
              className="w-full h-auto"
            />
          </div>
        ) : (
          <div className="flex justify-between items-center px-[.9rem] py-[.7rem] border border-[#757575] rounded-[8px] mt-[.4rem]">
            <Text_12_400_B3B3B3 className="leading-[1.05rem]">
              {example.output}
            </Text_12_400_B3B3B3>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <BudForm
      data={{}}
      backText="Back"
      onBack={() => {
        openDrawerWithStep("select-evaluation");
      }}
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <div className="flex items-start justify-between w-full p-[1.35rem]">
            <div className="flex items-start justify-start max-w-[72%]">
              <div className="p-[.6rem] w-[2.8rem] h-[2.8rem] bg-[#1F1F1F] rounded-[6px] mr-[1.05rem] shrink-0 grow-0 flex items-center justify-center">
                <Text_14_600_FFFFFF>📊</Text_14_600_FFFFFF>
              </div>
              <div>
                <Text_14_400_EEEEEE className="mb-[0.65rem] leading-[140%]">
                  {evaluationData.name}
                </Text_14_400_EEEEEE>
                <div className="flex flex-wrap gap-2">
                  {evaluationData.traits.slice(0, 3).map((trait, index) => (
                    <Tag
                      key={index}
                      className="bg-[#1F1F1F] border-[#2A2A2A] text-[#757575] px-2 py-0.5 text-[10px] rounded"
                    >
                      {trait}
                    </Tag>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex justify-end items-start">
              <CustomDropDown
                isDisabled={isExpandedViewOpen}
                buttonContent={
                  <div className="px-[.3rem] my-[0] py-[0.02rem]">
                    <Image
                      preview={false}
                      src="/images/drawer/threeDots.png"
                      alt="info"
                      style={{ width: "0.1125rem", height: ".6rem" }}
                    />
                  </div>
                }
                items={[
                  {
                    key: "1",
                    label: (
                      <Text_12_400_EEEEEE>View Details</Text_12_400_EEEEEE>
                    ),
                    onClick: () =>
                      window.open(evaluationData.websiteUrl, "_blank"),
                  },
                  {
                    key: "2",
                    label: <Text_12_400_EEEEEE>View Paper</Text_12_400_EEEEEE>,
                    onClick: () => window.open("#", "_blank"),
                  },
                ]}
              />
            </div>
          </div>

          <div className="px-[1.4rem]">
            {loading ? (
              <div className="flex justify-center items-center py-8">
                <Text_12_400_757575>
                  Loading evaluation details...
                </Text_12_400_757575>
              </div>
            ) : (
              <div className="pt-[.25rem]">
                {/* Description Section */}
                {evaluationData.description && (
                  <>
                    <div className="pt-[1.3rem]">
                      <div
                        ref={descriptionRef}
                        className={`leading-[1.05rem] tracking-[.01em max-w-[100%] ${isExpanded ? "" : "line-clamp-2"} overflow-hidden`}
                        style={{
                          display: "-webkit-box",
                          WebkitBoxOrient: "vertical",
                        }}
                      >
                        <Text_12_400_B3B3B3 className="leading-[180%]">
                          {evaluationData.description}
                        </Text_12_400_B3B3B3>
                      </div>
                      {isOverflowing && (
                        <div className="flex justify-end">
                          <Text_12_600_EEEEEE
                            className="cursor-pointer leading-[1.05rem] tracking-[.01em] mt-[.3rem]"
                            onClick={toggleDescription}
                          >
                            {isExpanded ? "See less" : "See more"}
                          </Text_12_600_EEEEEE>
                        </div>
                      )}
                    </div>
                    <div className="hR mt-[1.1rem]"></div>
                  </>
                )}

                {/* Links Section */}
                <div className="pt-[1.3rem]">
                  <Text_14_400_EEEEEE>Links</Text_14_400_EEEEEE>
                  <Text_12_400_757575 className="pt-[.45rem]">
                    External resources and references
                  </Text_12_400_757575>
                  <div className="flex flex-col gap-2 mt-[1rem]">
                    <div className="flex items-center gap-2">
                      <Text_12_400_757575>Author:</Text_12_400_757575>
                      <a
                        href={evaluationData.authorUrl}
                        className="text-[#4169E1] text-xs flex items-center gap-1 hover:underline"
                      >
                        {evaluationData.author}
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                    <div className="flex items-center gap-2">
                      <Text_12_400_757575>Website:</Text_12_400_757575>
                      <a
                        href={evaluationData.websiteUrl}
                        className="text-[#4169E1] text-xs flex items-center gap-1 hover:underline"
                      >
                        {evaluationData.website}
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                    <div className="flex items-center gap-2">
                      <Text_12_400_757575>Paper:</Text_12_400_757575>
                      <Text_12_400_EEEEEE>
                        {evaluationData.paper}
                      </Text_12_400_EEEEEE>
                    </div>
                  </div>
                </div>
                <div className="hR mt-[1.5rem]"></div>

                {/* Traits Section */}
                <div className="pt-[1.3rem]">
                  <Text_14_400_EEEEEE>
                    Evaluation Characteristics
                  </Text_14_400_EEEEEE>
                  <Text_12_400_757575 className="pt-[.45rem]">
                    Categories and attributes of this evaluation
                  </Text_12_400_757575>

                  {/* Domains */}
                  {evaluationData.traits.length > 0 && (
                    <div className="mt-[1rem]">
                      <Text_12_400_757575 className="mb-2">
                        Domains:
                      </Text_12_400_757575>
                      <div className="flex flex-wrap gap-2">
                        {evaluationData.traits.map((trait, index) => (
                          <Tag
                            key={`domain-${index}`}
                            className="bg-[#1F1F1F] border-[#2A2A2A] text-[#757575] px-3 py-1 text-xs rounded-md"
                          >
                            {trait}
                          </Tag>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Languages */}
                  {evaluationData.language.length > 0 && (
                    <div className="mt-[1rem]">
                      <Text_12_400_757575 className="mb-2">
                        Languages:
                      </Text_12_400_757575>
                      <div className="flex flex-wrap gap-2">
                        {evaluationData.language.map((lang, index) => (
                          <Tag
                            key={`lang-${index}`}
                            className="bg-[#1F1F1F] border-[#2A2A2A] text-[#757575] px-3 py-1 text-xs rounded-md"
                          >
                            {lang}
                          </Tag>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Modalities */}
                  {evaluationData.modalities.length > 0 && (
                    <div className="mt-[1rem]">
                      <Text_12_400_757575 className="mb-2">
                        Modalities:
                      </Text_12_400_757575>
                      <div className="flex flex-wrap gap-2">
                        {evaluationData.modalities.map((modality, index) => (
                          <Tag
                            key={`modality-${index}`}
                            className="bg-[#1F1F1F] border-[#2A2A2A] text-[#757575] px-3 py-1 text-xs rounded-md"
                          >
                            {modality}
                          </Tag>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Task Types */}
                  {evaluationData.task_type.length > 0 && (
                    <div className="mt-[1rem]">
                      <Text_12_400_757575 className="mb-2">
                        Task Types:
                      </Text_12_400_757575>
                      <div className="flex flex-wrap gap-2">
                        {evaluationData.task_type.map((task, index) => (
                          <Tag
                            key={`task-${index}`}
                            className="bg-[#1F1F1F] border-[#2A2A2A] text-[#757575] px-3 py-1 text-xs rounded-md"
                          >
                            {task}
                          </Tag>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Token Estimates */}
                  {(evaluationData.estimated_input_tokens > 0 ||
                    evaluationData.estimated_output_tokens > 0) && (
                    <div className="mt-[1rem]">
                      <Text_12_400_757575 className="mb-2">
                        Token Estimates:
                      </Text_12_400_757575>
                      <div className="flex gap-4">
                        {evaluationData.estimated_input_tokens > 0 && (
                          <div className="flex items-center gap-2">
                            <Text_12_400_757575>Input:</Text_12_400_757575>
                            <Text_12_400_EEEEEE>
                              {evaluationData.estimated_input_tokens.toLocaleString()}
                            </Text_12_400_EEEEEE>
                          </div>
                        )}
                        {evaluationData.estimated_output_tokens > 0 && (
                          <div className="flex items-center gap-2">
                            <Text_12_400_757575>Output:</Text_12_400_757575>
                            <Text_12_400_EEEEEE>
                              {evaluationData.estimated_output_tokens.toLocaleString()}
                            </Text_12_400_EEEEEE>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
                <div className="hR mt-[1.5rem]"></div>

                {/* Advantages Section */}
                {evaluationData.advantages.length > 0 && (
                  <>
                    <div className="pt-[1.5rem] mb-[1.4rem]">
                      <div>
                        <Text_14_400_EEEEEE>Advantages</Text_14_400_EEEEEE>
                        <Text_12_400_757575 className="pt-[.45rem]">
                          Delivering a full-list of advantages of the evaluation
                        </Text_12_400_757575>
                      </div>
                      <ul className="custom-bullet-list mt-[.9rem]">
                        {evaluationData.advantages.map((item, index) => (
                          <li key={index}>
                            <Text_12_400_EEEEEE className="leading-[1.3rem] indent-0 pl-[.5rem]">
                              {item}
                            </Text_12_400_EEEEEE>
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div className="hR"></div>
                  </>
                )}

                {/* Disadvantages Section */}
                {evaluationData.disadvantages.length > 0 && (
                  <>
                    <div className="pt-[1.5rem] mb-[1.4rem]">
                      <div>
                        <Text_14_400_EEEEEE>Disadvantages</Text_14_400_EEEEEE>
                        <Text_12_400_757575 className="pt-[.45rem]">
                          Delivering a full-list of disadvantages of the
                          evaluation
                        </Text_12_400_757575>
                      </div>
                      <ul className="custom-bullet-list mt-[.9rem]">
                        {evaluationData.disadvantages.map((item, index) => (
                          <li key={index}>
                            <Text_12_400_EEEEEE className="leading-[1.3rem] indent-0 pl-[.5rem]">
                              {item}
                            </Text_12_400_EEEEEE>
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div className="hR"></div>
                  </>
                )}

                {/* Examples Section */}
                {evaluationData.examples?.length > 0 && (
                  <>
                    <div className="mt-[1.4rem] mb-[1.4rem]">
                      <Text_14_400_EEEEEE>Examples</Text_14_400_EEEEEE>
                      <Text_12_400_757575 className="pt-[.9rem]">
                        These could input output text or Images, Audio or video.
                        This section is only shown if its available.
                      </Text_12_400_757575>
                      {evaluationData.examples.map((item, index) =>
                        renderExample(item, index),
                      )}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
