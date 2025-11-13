/* eslint-disable react/no-unescaped-entities */
import BarChart from "@/components/charts/barChart";
import GaugeChart from "@/components/charts/gaugeChart";
import ScoreChart from "@/components/charts/scoreChart";
import { errorToast, successToast } from "@/components/toast";
import { copyToClipboard } from "@/utils/clipboard";
import { ButtonInput } from "@/components/ui/button";
import { SelectInput } from "@/components/ui/input";
import {
  Text_12_400_C7C7C7,
  Text_12_500_111113,
  Text_14_400_5B6168,
  Text_14_400_FFFFFF,
} from "@/components/ui/text";
import {
  ChatBubbleIcon,
  InfoCircledIcon,
  Pencil1Icon,
  TrashIcon,
} from "@radix-ui/react-icons";
import {
  Box,
  Flex,
  Grid,
  Heading,
  Link,
  Table,
  Text,
  Tooltip,
} from "@radix-ui/themes";
import Image from "next/image";
import { useRouter } from "next/router";
import { useCallback, useEffect, useState } from "react";
import { AppRequest } from "src/pages/api/requests";
import DashBoardLayout from "src/pages/home/layout";
import DeleteDialog from "@/components/popups/_common/deletePopup";
import LineChart from "../../../../../../components/charts/lineChart";
import endpointIcon from "./../../../../../../../public/icons/endpoint.png";
import lArrowIcn from "./../../../../../../../public/icons/l-arrow.png";
import latencyIcon from "./../../../../../../../public/icons/latencyIcon.png";
import { useLoader } from "src/context/appContext";
import ToolTip from "@/components/ui/toolTip";

export default function EndpointDashboard() {
  const scoreDataProps = {
    harmfulness: {
      title: "Harmfulness",
      inputValue: 0,
      outputValue: 0,
      color: "#FFC442",
    },
    hallucination: {
      title: "Hallucinations",
      inputValue: 0,
      outputValue: 0,
      color: "#61A560",
    },
    sensitiveInformation: {
      title: "Sensitive Information",
      inputValue: 0,
      outputValue: 0,
      color: "#3F8EF7",
    },
    promptInjection: {
      title: "Prompt Injection",
      inputValue: 0,
      outputValue: 0,
      color: "#D45453",
    },
  };

  const tokenUsageDataProps = {
    categories: [],
    data: [],
    label1: "Tokens",
    label2: "Time",
    color: "#61A560",
    smooth: false,
  };

  const computeHoursDataProps = {
    categories: [],
    data: [],
    label1: "Compute (hrs)",
    label2: "Time (daily)",
    color: "#FFC442",
    smooth: true,
  };

  const apiCallsChartDataProps = {
    categories: [],
    data: [],
    label1: "API Calls",
    label2: "Date",
  };
  const { isLoading, showLoader, hideLoader } = useLoader();

  const router = useRouter();
  const [projectId, setProjectId] = useState(null);
  const [projectDetails, setProjectDetails] = useState(null);
  const [endpointId, setEndpointId] = useState(null);
  const [endpointDetailsData, setEndpointDetailsData] = useState(null);
  const [scoreProps, setScoreProps] = useState(scoreDataProps);
  const [tokenUsageProps, setTokenUsageProps] = useState(tokenUsageDataProps);
  const [computeHoursProps, setComputeHoursProps] = useState(
    computeHoursDataProps,
  );
  const [apiCallsProps, setApiCallsProps] = useState(apiCallsChartDataProps);
  const [latencyData, setLatencyData] = useState(null);
  const [promptUsageData, setPromptUsageData] = useState(null);
  const [selectedRowData, setSelectedRowData] = useState<FormData | null>(null);
  const [isDeleteEndpointOpen, setIsDeleteEndpointOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [isEditOpen, setIsEditgOpen] = useState(false);
  const getProjectDetails = useCallback(async () => {
    try {
      const response: any = await AppRequest.Get(`/projects/${projectId}`);
      setProjectDetails(response.data.result);
      successToast(response.message);
    } catch (error) {
      console.error("Error creating model:", error);
    }
  }, [projectId]);

  const getEndpointDetails = useCallback(async () => {
    if (endpointId) {
      showLoader();
      try {
        const response: any = await AppRequest.Get(
          `/endpoints/${endpointId}/status`,
        );
        setEndpointDetailsData(response.data.result);
        hideLoader();
      } catch (error) {
        console.error("Error creating model:", error);
      }
    }
  }, [endpointId]);

  const getScoreData = useCallback(async () => {
    if (endpointId) {
      try {
        const response: any = await AppRequest.Get(
          `/metrics/scoring-result/${endpointId}?entity=endpoint`,
        );
        if (response.data.result) {
          setScoreProps((scoreProps) => ({
            ...scoreProps,
            harmfulness: {
              ...scoreProps.harmfulness,
              inputValue: response.data.result?.["harmfulness_input"] ?? 0,
              outputValue: response.data.result?.["harmfulness_output"] ?? 0,
            },
            hallucination: {
              ...scoreProps.hallucination,
              inputValue: response.data.result?.["hallucination_inputput"] ?? 0,
              outputValue: response.data.result?.["hallucination_output"] ?? 0,
            },
            sensitiveInformation: {
              ...scoreProps.sensitiveInformation,
              inputValue: response.data.result?.["sensitive_info_input"] ?? 0,
              outputValue: response.data.result?.["sensitive_info_output"] ?? 0,
            },
            promptInjection: {
              ...scoreProps.promptInjection,
              inputValue: response.data.result?.["prompt_injection_input"] ?? 0,
              outputValue:
                response.data.result?.["prompt_injection_output"] ?? 0,
            },
          }));
        }
      } catch (error) {
        console.error("Error creating model:", error);
      }
    }
  }, [endpointId]);

  const getTokeUsageData = useCallback(async () => {
    if (endpointId) {
      try {
        const response: any = await AppRequest.Get(
          `/metrics/token-usage/${endpointId}?entity=endpoint`,
        );
        if (response.data.result) {
          setTokenUsageProps((tokenUsageProps) => ({
            ...tokenUsageProps,
            title: "Token Usage",
            categories: response.data.result?.["x"],
            data: response.data.result?.["y"],
          }));
        }
      } catch (error) {
        console.error("Error creating model:", error);
      }
    }
  }, [endpointId]);

  const getComputeHoursData = useCallback(async () => {
    if (endpointId) {
      try {
        const response: any = await AppRequest.Get(
          `/metrics/compute-hours/${endpointId}?entity=endpoint`,
        );
        if (response.data.result) {
          setComputeHoursProps((computeHoursProps) => ({
            ...computeHoursProps,
            title: "Compute Hours",
            categories: response.data.result?.["x"],
            data: response.data.result?.["y"],
          }));
        }
      } catch (error) {
        console.error("Error creating model:", error);
      }
    }
  }, [endpointId]);

  const getApiCallsData = useCallback(async () => {
    if (endpointId) {
      try {
        const response: any = await AppRequest.Get(
          `/metrics/request-count/${endpointId}?entity=endpoint`,
        );
        if (response.data.result) {
          setApiCallsProps((apiCallsProps) => ({
            ...apiCallsProps,
            title: "No. of API calls",
            categories: response.data.result?.["x"],
            data: response.data.result?.["y"],
          }));
        }
      } catch (error) {
        console.error("Error creating model:", error);
      }
    }
  }, [endpointId]);

  const getLatencyData = useCallback(async () => {
    if (endpointId) {
      try {
        const response: any = await AppRequest.Get(
          `/metrics/cache-analytics/${endpointId}?entity=endpoint`,
        );
        setLatencyData(response.data.result);
      } catch (error) {
        console.error("Error creating model:", error);
      }
    }
  }, [endpointId]);

  const getPromptUsageData = useCallback(async () => {
    if (endpointId) {
      try {
        const response: any = await AppRequest.Get(
          `/metrics/reused-prompts/${endpointId}?entity=endpoint`,
        );
        setPromptUsageData(response.data.results);
      } catch (error) {
        console.error("Error creating model:", error);
      }
    }
  }, [endpointId]);

  const copyEndpoint = async (name: string, value: any) => {
    const curl = `curl --location '${process.env.NEXT_PUBLIC_BASE_URL}v1/chat/completions' \\
                  --header 'Authorization: Bearer {API_KEY_HERE}' \\
                  --header 'Content-Type: application/json' \\
                  --data '{
                    "model": '${endpointDetailsData.model.name}',
                    "max_tokens": "256",
                    "messages": [{"role": "user", "content": "Summarize the given text"}]
                  }'`;
    const python = `import requests
                    import json

                    url = "${process.env.NEXT_PUBLIC_BASE_URL}v1/chat/completions"

                    payload = json.dumps({
                      "model": ${endpointDetailsData.model.name},
                      "max_tokens": "10",
                      "messages": [
                        {
                          "role": "user",
                          "content": "Summarize the given text"
                        }
                      ]
                    })
                    headers = {
                      'Authorization: Bearer {API_KEY_HERE}',
                      'Content-Type': 'application/json'
                    }

                    response = requests.request("POST", url, headers=headers, data=payload)

                    print(response.text)`;
    const js = `// WARNING: For POST requests, body is set to null by browsers.
                var data = JSON.stringify({
                  "model": ${endpointDetailsData.model.name},
                  "max_tokens": "10",
                  "messages": [
                    {
                      "role": "user",
                      "content": "Summarize the given text"
                    }
                  ]
                });

                var xhr = new XMLHttpRequest();
                xhr.withCredentials = true;

                xhr.addEventListener("readystatechange", function() {
                  if(this.readyState === 4) {
                    console.log(this.responseText);
                  }
                });

                xhr.open("POST", "${process.env.NEXT_PUBLIC_BASE_URL}v1/chat/completions");
                xhr.setRequestHeader('Authorization: Bearer {API_KEY_HERE}');
                xhr.setRequestHeader("Content-Type", "application/json");

                xhr.send(data);`;

    let text;
    if (value === "Copy for curl") {
      text = curl;
    } else if (value === "Copy for python") {
      text = python;
    } else if (value === "Copy for javascript") {
      text = js;
    }

    await copyToClipboard(text, {
      onSuccess: () => successToast("Copied.."),
      onError: () => errorToast("Failed to copy"),
    });
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
    getEndpointDetails();
    getScoreData();
    getTokeUsageData();
    getComputeHoursData();
    getApiCallsData();
    getLatencyData();
    getPromptUsageData();
  }, [
    endpointId,
    getEndpointDetails,
    getScoreData,
    getTokeUsageData,
    getComputeHoursData,
    getApiCallsData,
    getLatencyData,
    getPromptUsageData,
  ]);

  const hitRatio = {
    title: "HIT Ratio",
    value: latencyData?.cache_ratio * 100,
    color: "#FFC442",
    proportion: 1.0,
  };

  const globalFilters = {
    endpointId: router.query.endpointId,
    startDate: "",
    endDate: "",
  };

  // modal popup handling
  const handleOpenDialogDeleteEndpoint = () => {
    setIsDeleteEndpointOpen(true);
  };
  const handleCloseDialogDelete = () => {
    setIsDeleteOpen(false);
    setIsDeleteEndpointOpen(false);
  };
  const handleOpenDialogEdit = () => {
    setIsEditgOpen(true);
  };

  const capitalizeFirstLetter = (input) => {
    // Convert the input to a string if it isn't one
    const string = String(input || "");

    // Replace any special characters with an empty space
    const sanitizedString = string.replace(/[^a-zA-Z0-9\s]/g, " ");

    // Capitalize the first letter and return
    return sanitizedString.charAt(0).toUpperCase() + sanitizedString.slice(1);
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
            <Text_14_400_FFFFFF>&nbsp;Endpoint details</Text_14_400_FFFFFF>
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
              handleOpenDialogDeleteEndpoint();
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
          <Box mb="5">
            <Flex direction="row" gap="2" mb="3">
              <Box p="1">
                <Image
                  width={20}
                  className="endpointIcon"
                  src={endpointIcon}
                  alt="Endpoint Icon"
                />
              </Box>
              <Text as="div" size="6" mb="0" weight="medium">
                {endpointDetailsData?.model.name}
              </Text>
              <ToolTip
                triggerRenderItem={
                  <InfoCircledIcon className="w-4 h-4 align-middle mt-1 text-gray-500" />
                }
                arrowClasses="!fill-[#111113] stroke-2 !stroke-[#212225]"
                align="center"
                renderItemClassName="!bg-[#111113] !border !border-[1px] !border-[#212225] !rounded-md max-h-[2.1875rem]"
                contentRenderItem={
                  <Text_14_400_5B6168 className="text-[#6A6E76]">
                    Created by {endpointDetailsData?.created_user.email}
                  </Text_14_400_5B6168>
                }
              />
            </Flex>
            {endpointDetailsData && (
              <Flex direction="row" gap="2" mb="3">
                <Box className="rounded-lg border border-[#2F3135] px-[.35rem] py-[.3rem] mr-[.1rem] cursor-pointer hover:bg-[#18191B] block">
                  <Text_12_400_C7C7C7>
                    {capitalizeFirstLetter(endpointDetailsData?.model.type)}
                  </Text_12_400_C7C7C7>
                </Box>
                <Box className="rounded-lg border border-[#2F3135] px-[.35rem] py-[.3rem] mr-[.1rem] cursor-pointer hover:bg-[#18191B] block">
                  <Text_12_400_C7C7C7>
                    {capitalizeFirstLetter(endpointDetailsData?.cluster.name)}
                  </Text_12_400_C7C7C7>
                </Box>
                <Box className="rounded-lg border border-[#2F3135] px-[.35rem] py-[.3rem] mr-[.1rem] cursor-pointer hover:bg-[#18191B] block">
                  <Text_12_400_C7C7C7>
                    {capitalizeFirstLetter(endpointDetailsData?.replicas)}{" "}
                    worker{`${endpointDetailsData.replicas > 1 ? "s" : ""}`}
                  </Text_12_400_C7C7C7>
                </Box>
                <Box
                  className={`rounded-lg border border-[#2F3135] px-[.35rem] py-[.3rem] mr-[.1rem] cursor-pointer ${endpointDetailsData?.status.toLowerCase() === "running" ? "bg-[#61A560]" : "bg-red-500"} hover:bg-[#18191B] block`}
                >
                  <Text_12_500_111113>
                    {capitalizeFirstLetter(endpointDetailsData?.status)}
                  </Text_12_500_111113>
                </Box>
              </Flex>
            )}

            <Flex direction="row" gap="2">
              <label className="bold -w-[200px]">
                <SelectInput
                  size="2"
                  value="Use this endpoint"
                  onValueChange={(value) => copyEndpoint("endPoint", value)}
                  triggerClassName=""
                  placeholder="Use this endpoint"
                  showSearch={false}
                  selectItems={[
                    "Copy for curl",
                    "Copy for python",
                    "Copy for javascript",
                  ]}
                  renderItem=""
                />
              </label>
            </Flex>
          </Box>
          <Grid
            columns="2"
            gap="3"
            rows="repeat(2,225px)"
            width="auto"
            justify="between"
          >
            <Box className="rounded-md min-w-48">
              <ScoreChart data={scoreProps} />
            </Box>
            <Box className="bg-neutral-900 rounded-md min-w-48">
              <LineChart data={tokenUsageProps} />
            </Box>
            <Box className="bg-neutral-900 rounded-md min-w-48">
              <LineChart data={computeHoursProps} />
            </Box>
            <Box className="bg-neutral-900 rounded-md min-w-48">
              <BarChart data={apiCallsProps} />
            </Box>
          </Grid>

          <Heading size="5" weight="medium" trim="normal" className="mb-4 mt-6">
            Cache Analytics
          </Heading>
          <Box height="200px" width="500px" className="w-3/5 align-middle">
            <Flex direction="column" gap="2">
              <Flex direction="row" gap="2" justify="between">
                <Box className="bg-neutral-900 rounded-md w-2/3 h-108px py-4 px-4 inline-block align-middle">
                  <Flex gap="3" justify="center" className="align-middle">
                    <Image
                      className="w-[73px] h-[73px] align-middle my-auto"
                      src={latencyIcon}
                      alt="latency Icon"
                    />
                    <Flex
                      direction="column"
                      justify="between"
                      align="center"
                      className="align-middle"
                    >
                      <Text size="9">
                        {latencyData?.cache_latency ?? `-`} ms
                      </Text>
                      <Text size="5">Cache Latency</Text>
                    </Flex>
                  </Flex>
                </Box>
                <Box className="bg-neutral-900 rounded-md w-1/3 h-108px py-4 px-4">
                  <GaugeChart props={hitRatio} />
                </Box>
              </Flex>

              <Box className="bg-neutral-900 rounded-md min-w-48">
                <Flex direction="column">
                  <Text mt="5" ml="6">
                    Most used prompts
                  </Text>
                  <Table.Root
                    variant="ghost"
                    ml="5"
                    size="2"
                    className="text-sm"
                  >
                    <Table.Header>
                      <Table.Row>
                        <Table.ColumnHeaderCell>Prompts</Table.ColumnHeaderCell>
                        <Table.ColumnHeaderCell>Reused</Table.ColumnHeaderCell>
                      </Table.Row>
                    </Table.Header>
                    <Table.Body>
                      {promptUsageData?.map((item, index) => (
                        <Table.Row key={index}>
                          <Table.RowHeaderCell>
                            {item.prompt}
                          </Table.RowHeaderCell>
                          <Table.Cell>{item.reused_count}</Table.Cell>
                          {/* Add more Td components for additional columns */}
                        </Table.Row>
                      ))}
                    </Table.Body>
                  </Table.Root>
                </Flex>
              </Box>
            </Flex>
          </Box>
        </div>
      </div>
    </DashBoardLayout>
  );
}
