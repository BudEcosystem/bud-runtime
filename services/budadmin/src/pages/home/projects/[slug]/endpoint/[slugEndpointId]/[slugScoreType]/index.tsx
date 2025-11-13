import { ButtonInput } from "@/components/ui/button";
import { Text_14_400_5B6168, Text_14_400_FFFFFF } from "@/components/ui/text";
import {
  ChatBubbleIcon,
  ChevronLeftIcon,
  CopyIcon,
  Pencil1Icon,
  TrashIcon,
} from "@radix-ui/react-icons";
import {
  DropdownMenu,
  Flex,
  Heading,
  IconButton,
  Link,
  Table,
  Text,
} from "@radix-ui/themes";
import Image from "next/image";
import { useRouter } from "next/router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AppRequest } from "src/pages/api/requests";
import DashBoardLayout from "src/pages/home/layout";
import lArrowIcn from "./../../../../../../../../public/icons/l-arrow.png";
import { errorToast, successToast } from "@/components/toast";
import { copyToClipboard } from "@/utils/clipboard";

const setScoreTypeTitle = (scoreType) => {
  switch (scoreType) {
    case "harmfulness":
      return "Harmfulness";
    case "hallucination":
      return "Hallucination";
    case "sensitive_info":
      return "Sensitive Information";
    case "prompt_injection":
      return "Prompt Injection";
    default:
      return null;
  }
};

const filterScoreData = (data, scoreType) => {
  const filteredData = data.filter((item) => {
    return item.type === scoreType;
  });
  return filteredData[0];
};
interface ScoreDetail {
  type: string | null;
  title?: string;
  data: any[];
}

const PromptScoreDetail = () => {
  const router = useRouter();

  const defaultData = useMemo(
    () => ({
      type: null,
      title: "",
      data: [],
    }),
    [],
  );

  const [projectId, setProjectId] = useState(null);
  const [endpointId, setEndpointId] = useState(null);
  const [scoreType, setScoreType] = useState(null);
  const [promptScoreTableData, setPromptScoreTableData] = useState(defaultData);
  const scoringType = {
    harmfulness: "harmfulness",
    sensitive_info: "sensitive_info",
    prompt_injection: "prompt_injection_input",
    hallucination: "hallucination_output",
  };

  useEffect(() => {
    if (router.query.projectId) {
      setProjectId(
        Array.isArray(router.query.projectId)
          ? router.query.projectId[0]
          : router.query.projectId,
      );
    }
  }, [router.query.projectId]);

  useEffect(() => {
    if (router.query.endpointId) {
      setEndpointId(
        Array.isArray(router.query.endpointId)
          ? router.query.endpointId[0]
          : router.query.endpointId,
      );
    }
  }, [router.query.endpointId]);

  useEffect(() => {
    if (router.query.scoreType) {
      setScoreType(
        Array.isArray(router.query.scoreType)
          ? router.query.scoreType[0]
          : router.query.scoreType,
      );
    }
  }, [router.query.scoreType]);

  useEffect(() => {
    if (scoreType) {
      setPromptScoreTableData(defaultData);
    }
  }, [scoreType, defaultData]);

  const getPromptUsageData = useCallback(async () => {
    if (!endpointId || !scoreType) return;

    try {
      const response: any = await AppRequest.Get(
        `/endpoints/${endpointId}/interactions?scoring_result=${scoringType[scoreType]}`,
      );
      if (response.data.results) {
        const transformedData = response.data.results.map((item) => ({
          prompt: item.prompt,
          response: item.response,
          scores: [
            {
              harmfulness:
                ((item.harmfulness_input ?? 0) +
                  (item.harmfulness_output ?? 0)) /
                2,
            },
            {
              sensitive_info:
                ((item.sensitive_info_input ?? 0) +
                  (item.sensitive_info_output ?? 0)) /
                2,
            },
            {
              prompt_injection:
                item.prompt_injection_input ||
                item.prompt_injection_output ||
                0,
            },
            {
              hallucination:
                item.hallucination_output || item.hallucination_output || 0,
            },
          ],
        }));

        setPromptScoreTableData({
          type: scoreType,
          title: setScoreTypeTitle(scoreType),
          data: transformedData,
        });
      }
    } catch (error) {
      console.error("Error fetching prompt usage data:", error);
    }
  }, [endpointId, scoreType]);

  useEffect(() => {
    if (endpointId) {
      getPromptUsageData();
    }
  }, [endpointId, getPromptUsageData]);

  const [selectedRowData, setSelectedRowData] = useState<FormData | null>(null);
  const [isDeleteEndpointOpen, setIsDeleteEndpointOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [isAddUserOpen, setIsAddUserOpen] = useState(false);
  const [isEditOpen, setIsEditgOpen] = useState(false);
  const [isDeleteProjectOpen, setIsDeleteProjectOpen] = useState(false);
  const [hoveredRow, setHoveredRow] = useState(null);

  // modal popup handling
  const handleOpenDialogDeleteEndpoint = (item: any) => {
    setSelectedRowData(item);
    setIsDeleteEndpointOpen(true);
  };
  const handleCloseDialogDelete = () => {
    setIsDeleteOpen(false);
    setIsDeleteEndpointOpen(false);
  };
  const handleOpenDialogEdit = () => {
    setIsEditgOpen(true);
  };
  const handleOpenDialogDeleteProject = () => {
    setIsDeleteProjectOpen(true);
  };

  const handleMouseEnter = (rowIndex) => {
    setHoveredRow(rowIndex);
  };

  const handleMouseLeave = () => {
    setHoveredRow(null);
  };

  const handleCopyContent = async (type: string, item: any) => {
    let text;
    if (type === "prompt") {
      text = item.prompt;
    } else if (type === "response") {
      text = item.response;
    } else if (type === "both") {
      text = `Prompt: ${item.prompt}\nResponse: ${item.response}`;
    }

    await copyToClipboard(text, {
      onSuccess: () => successToast("Copied.."),
      onError: () => errorToast("Failed to copy"),
    });
  };

  const HeaderContent = () => {
    return (
      <Flex align="center" justify="between">
        <Flex align="center" justify="start">
          <Flex
            align="center"
            justify="center"
            className="rounded rounded-full bg-[#18191B] w-[1.75rem] h-[1.75rem] shadow-[0_0_2px_2px_rgba(0, 0, 0, 0.85))] hover:border hover:border-[#120f0f] cursor-pointer mr-[.5rem]"
            onClick={router.back}
          >
            <Image
              width={20}
              className="w-[.5rem] h-[.8rem]"
              src={lArrowIcn}
              alt="Logo"
            />
          </Flex>
          <Flex>
            <Link href="/projects">
              <Text_14_400_5B6168>Projects /</Text_14_400_5B6168>
            </Link>
            <Link href={`/projects/${projectId}`}>
              <Text_14_400_5B6168>&nbsp; Project details /</Text_14_400_5B6168>
            </Link>
            <Link href={`/projects/${projectId}/endpoint/${endpointId}`}>
              <Text_14_400_5B6168>&nbsp; Endpoint details /</Text_14_400_5B6168>
            </Link>
            <Text_14_400_FFFFFF className="!text-[#965CDE]">
              &nbsp;
              {setScoreTypeTitle(scoreType)
                ? `${setScoreTypeTitle(scoreType)} prompt list`
                : `Score not found`}
            </Text_14_400_FFFFFF>
          </Flex>
        </Flex>
        <Flex align="center" justify="end" gap="1">
          <ButtonInput
            className="group bg-transparent px-[0rem] py-[0rem] h-[1.3rem] w-[1.3rem] border-0 hover:border-0 hover:border-transparent"
            onClick={(event) => {
              event.stopPropagation();
            }}
          >
            <ChatBubbleIcon className="text-[#5B6168] group-hover:text-[#FFFFFF]" />
          </ButtonInput>
          <ButtonInput
            className="group bg-transparent px-[0rem] py-[0rem] h-[1.3rem] w-[1.3rem] border-0 hover:border-0 hover:border-transparent"
            onClick={(event) => {
              event.stopPropagation();
              handleOpenDialogEdit();
            }}
          >
            <Pencil1Icon className="text-[#5B6168] group-hover:text-[#FFFFFF]" />
          </ButtonInput>
          <ButtonInput
            className="group bg-transparent px-[0rem] py-[0rem] h-[1.3rem] w-[1.3rem] border-0 hover:border-0 hover:border-transparent"
            onClick={(event) => {
              event.stopPropagation();
              handleOpenDialogDeleteProject();
            }}
          >
            <TrashIcon className="text-[#5B6168] group-hover:text-[#FFFFFF]" />
          </ButtonInput>
        </Flex>
      </Flex>
    );
  };

  return (
    <DashBoardLayout headerItems={<HeaderContent />}>
      <div className="boardPageView">
        <div className="boardPageTop">
          {setScoreTypeTitle(scoreType) ? (
            <Flex direction="column">
              <Heading
                trim="normal"
                className="mb-4 mt-6 font-medium text-[1.68em]"
              >
                {setScoreTypeTitle(scoreType)
                  ? `${setScoreTypeTitle(scoreType)} prompt list`
                  : `Score not found`}
              </Heading>
              {promptScoreTableData.data?.length > 0 ? (
                <Table.Root ml="5" size="2" className="text-sm ml-0">
                  <Table.Header>
                    <Table.Row>
                      <Table.ColumnHeaderCell>Prompt</Table.ColumnHeaderCell>
                      <Table.ColumnHeaderCell>Response</Table.ColumnHeaderCell>
                      <Table.ColumnHeaderCell>Score</Table.ColumnHeaderCell>
                      <Table.ColumnHeaderCell></Table.ColumnHeaderCell>
                    </Table.Row>
                  </Table.Header>
                  <Table.Body>
                    {promptScoreTableData.data?.map((item, index) => (
                      <Table.Row
                        key={index}
                        className={`${hoveredRow === index && "bg-[#18191B]"}`}
                        onMouseEnter={() => handleMouseEnter(index)}
                        onMouseLeave={handleMouseLeave}
                      >
                        <Table.Cell className="!shadow-none text-xs text-[#B0B4BA] truncate max-w-[250px]">
                          {item.prompt}
                        </Table.Cell>
                        <Table.Cell className="!shadow-none text-xs text-[#B0B4BA] truncate max-w-[250px]">
                          {item.response}
                        </Table.Cell>
                        <Table.Cell className="!shadow-none text-xs text-[#B0B4BA] w-[400px]">
                          {item.scores?.find(
                            (score) => Object.keys(score)[0] === scoreType,
                          )?.[scoreType] != null
                            ? item.scores.find(
                                (score) => Object.keys(score)[0] === scoreType,
                              )?.[scoreType] * 100
                            : `NA`}
                        </Table.Cell>

                        <Table.Cell
                          className={`!shadow-none text-xs opacity-0 text-[#B0B4BA] text-nowrap ${hoveredRow === index && "opacity-100"}`}
                        >
                          <DropdownMenu.Root>
                            <DropdownMenu.Trigger className="group">
                              <CopyIcon></CopyIcon>
                            </DropdownMenu.Trigger>
                            <DropdownMenu.Content
                              variant="soft"
                              color="gray"
                              side="bottom"
                              align={"end"}
                            >
                              <DropdownMenu.Item
                                className="font-light"
                                onClick={() => {
                                  handleCopyContent("prompt", item);
                                }}
                              >
                                Copy prompt
                              </DropdownMenu.Item>
                              <DropdownMenu.Item
                                className="font-light"
                                onClick={() => {
                                  handleCopyContent("response", item);
                                }}
                              >
                                Copy response
                              </DropdownMenu.Item>
                              <DropdownMenu.Item
                                className="font-light"
                                onClick={() => {
                                  handleCopyContent("both", item);
                                }}
                              >
                                Copy both
                              </DropdownMenu.Item>
                            </DropdownMenu.Content>
                          </DropdownMenu.Root>
                        </Table.Cell>
                      </Table.Row>
                    ))}
                  </Table.Body>
                </Table.Root>
              ) : (
                <Text>No data found</Text>
              )}
            </Flex>
          ) : (
            <Text>No data found</Text>
          )}
        </div>
      </div>
    </DashBoardLayout>
  );
};

export default PromptScoreDetail;
