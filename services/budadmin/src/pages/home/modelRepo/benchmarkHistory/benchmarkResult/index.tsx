"use client";
import Image from "next/image";
import Breadcrumb from "@/components/breadcrumb";
import { SwitchInput } from "@/components/ui/input";
import {
  Text_10_400_FFFFFF,
  Text_12_300_44474D,
  Text_12_400_787B83,
  Text_18_700_FFFFFF,
  Text_24_700_FFFFFF,
  Text_26_600_FFFFFF,
  Text_8_400_FFFFFF,
} from "@/components/ui/text";
import { Box, Flex, Grid } from "@radix-ui/themes";
import { useRouter } from "next/router";
import React, { useEffect, useState } from "react";
import { AppRequest } from "src/pages/api/requests";
import DashBoardLayout from "src/pages/home/layout";
import latencyIcon from 'public/icons/latencyIcon.png'
import clockIcon from 'public/icons/clockIcon.png'
import stopwatchIcon from 'public/icons/stopwatchIcon.png'
import throughput from 'public/icons/throughput.png'
import timeSettingIcon from 'public/icons/timeSettingIcon.png'
import cacheIcon from 'public/icons/cacheIcon.png'
import tokenIcon from 'public/icons/tokenIcon.png'
type Props = {};

const BenchmarkHistory = (props: Props) => {
  const [isCacheEnabled, setIsCacheEnabled] = useState(false);
  const [benchmarkResult, setBenchmarkResult] = useState<any>({});
  const router = useRouter();
  const { benchmarkId } = router.query;

  const getBenchmarkResult = async () => {
    const response: any = await AppRequest.Get(`/benchmarks/${benchmarkId}`);
    setBenchmarkResult(response?.data?.result);
    setIsCacheEnabled(response?.data?.result?.use_cache);
  };
  useEffect(() => {
    if (benchmarkId) {
      getBenchmarkResult();
    } else {
      // router.push('/modelRepo/benchmarkHistory');
    }
  }, [benchmarkId]);

  return (
    <DashBoardLayout>
      <Breadcrumb previousRoute="/modelRepo/benchmarkHistory" />
      <Flex className="px-[5.1%]" align="center" justify="between">
        <Text_26_600_FFFFFF>Benchmark result</Text_26_600_FFFFFF>
      </Flex>
      <div className="boardPageView">
        <div className="boardMainContainer !h-[85%] custom-scrollbar scroll-smooth">
          <Flex gap={"5"} wrap={"wrap"} mb={"5"}>
            <div className="min-w-28">
              <Text_12_400_787B83 className="mb-3">Cluster</Text_12_400_787B83>
              <Text_12_300_44474D>
                {benchmarkResult?.cluster_name}
              </Text_12_300_44474D>
            </div>
            <div className="min-w-28">
              <Text_12_400_787B83 className="mb-3">
                Number of workers
              </Text_12_400_787B83>
              <Text_12_300_44474D>
                {benchmarkResult?.num_of_workers}
              </Text_12_300_44474D>
            </div>
            <div className="min-w-28">
              <Text_12_400_787B83 className="mb-3">
                Number of users
              </Text_12_400_787B83>
              <Text_12_300_44474D>
                {benchmarkResult?.num_of_users}
              </Text_12_300_44474D>
            </div>
            <div className="min-w-28">
              <Text_12_400_787B83 className="mb-3">
                Max Tokens
              </Text_12_400_787B83>
              <Text_12_300_44474D>
                {benchmarkResult?.max_new_tokens}
              </Text_12_300_44474D>
            </div>
          </Flex>
          {benchmarkResult?.use_cache && (
            <>
              <Flex align="center" gap="2" mb={"2"}>
                <Text_12_400_787B83>Cache</Text_12_400_787B83>
                <SwitchInput
                  disabled={true}
                  className="cursor-pointer"
                  checked={isCacheEnabled}
                ></SwitchInput>
              </Flex>
              <Flex gap={"5"} wrap={"wrap"} mb={"5"}>
                <div className="min-w-28">
                  <Text_12_400_787B83 className="mb-3">
                    Embedding Model
                  </Text_12_400_787B83>
                  <Text_12_300_44474D>
                    {benchmarkResult?.embedding_model}
                  </Text_12_300_44474D>
                </div>
                <div className="min-w-28">
                  <Text_12_400_787B83 className="mb-3">
                    Max Cache Size
                  </Text_12_400_787B83>
                  <Text_12_300_44474D>
                    {benchmarkResult?.max_size}
                  </Text_12_300_44474D>
                </div>
                <div className="min-w-28">
                  <Text_12_400_787B83 className="mb-3">
                    Scoring threshold
                  </Text_12_400_787B83>
                  <Text_12_300_44474D>
                    {benchmarkResult?.score_threshold || `-`}
                  </Text_12_300_44474D>
                </div>
                <div className="min-w-28">
                  <Text_12_400_787B83 className="mb-3">
                    Eviction policy
                  </Text_12_400_787B83>
                  <Text_12_300_44474D className="uppercase">
                    {benchmarkResult?.eviction_policy || `-`}
                  </Text_12_300_44474D>
                </div>
                <div className="min-w-28">
                  <Text_12_400_787B83 className="mb-3">
                    Days to Expire
                  </Text_12_400_787B83>
                  <Text_12_300_44474D>
                    {benchmarkResult?.ttl || `-`}
                  </Text_12_300_44474D>
                </div>
              </Flex>
            </>
          )}
          <div>
            <Flex gap="4">
              <Flex
                className="bg-[#18191B] px-5 py-4 rounded-[7px]"
                align="center"
              >
                <Image
                  width={20}
                  className="w-8 h-8 mr-2"
                  src={latencyIcon}
                  alt="Logo"
                />
                <div>
                  <Text_24_700_FFFFFF className="mb-1">
                    {benchmarkResult?.successful_requests}
                  </Text_24_700_FFFFFF>
                  <Text_10_400_FFFFFF>Successful requests</Text_10_400_FFFFFF>
                </div>
              </Flex>
              <Flex
                className="bg-[#18191B] px-5 py-4 rounded-[7px]"
                align="center"
              >
                <Image
                  width={20}
                  className="w-8 h-8 mr-2"
                  src={clockIcon}
                  alt="Logo"
                />
                <div>
                  <Text_24_700_FFFFFF className="mb-1">
                    {benchmarkResult?.duration} s
                  </Text_24_700_FFFFFF>
                  <Text_10_400_FFFFFF>Benchmark duration</Text_10_400_FFFFFF>
                </div>
              </Flex>
            </Flex>
            <Grid columns={{ initial: "1", md: "2" }} gap="3" width="auto">
              <Box className="bg-[#18191B] mt-4 px-5 pt-4 pb-8 rounded-[7px]">
                <Flex className="mb-3" align="center">
                  <Image
                    width={20}
                    className="w-[1.073125em] h-[0.95875em] mr-2"
                    src={stopwatchIcon}
                    alt="Logo"
                  />
                  <div className="text-[#61A560] font-medium text-sm">TTFT</div>
                </Flex>
                <Flex gap="6" className="mb-6">
                  <Flex className="mr-6" align="center">
                    <div>
                      <Text_18_700_FFFFFF className="mb-1">
                        {benchmarkResult?.mean_ttft_ms}{" "}
                        <span className="font-bold text-xs ">ms</span>
                      </Text_18_700_FFFFFF>
                      <Text_10_400_FFFFFF>Mean TTFT</Text_10_400_FFFFFF>
                    </div>
                  </Flex>
                  <Flex className="" align="center">
                    <div>
                      <Text_18_700_FFFFFF className="mb-1">
                        {benchmarkResult?.median_ttft_ms}{" "}
                        <span className="font-bold text-xs ">ms</span>
                      </Text_18_700_FFFFFF>
                      <Text_10_400_FFFFFF>Median TTFT</Text_10_400_FFFFFF>
                    </div>
                  </Flex>
                </Flex>
                <Flex gap="4" justify="between">
                  <Flex className="" align="center">
                    <div>
                      <Text_18_700_FFFFFF className="mb-1">
                        {benchmarkResult?.p25_ttft_ms}
                        <span className="font-bold text-xs ml-1">ms</span>
                      </Text_18_700_FFFFFF>
                      <Text_10_400_FFFFFF>25 Percentile</Text_10_400_FFFFFF>
                    </div>
                  </Flex>
                  <Flex className="" align="center">
                    <div>
                      <Text_18_700_FFFFFF className="mb-1">
                        {benchmarkResult?.p75_ttft_ms}
                        <span className="font-bold text-xs ml-1">ms</span>
                      </Text_18_700_FFFFFF>
                      <Text_10_400_FFFFFF>75 Percentile</Text_10_400_FFFFFF>
                    </div>
                  </Flex>
                  <Flex className="" align="center">
                    <div>
                      <Text_18_700_FFFFFF className="mb-1">
                        {benchmarkResult?.p95_ttft_ms}
                        <span className="font-bold text-xs ml-1">ms</span>
                      </Text_18_700_FFFFFF>
                      <Text_10_400_FFFFFF>95 Percentile</Text_10_400_FFFFFF>
                    </div>
                  </Flex>
                  <Flex className="" align="center">
                    <div>
                      <Text_18_700_FFFFFF className="mb-1">
                        {benchmarkResult?.p99_ttft_ms}
                        <span className="font-bold text-xs ml-1">ms</span>
                      </Text_18_700_FFFFFF>
                      <Text_10_400_FFFFFF>99 Percentile</Text_10_400_FFFFFF>
                    </div>
                  </Flex>
                </Flex>
              </Box>
              <Box className="bg-[#18191B] mt-4 px-5 pt-4 pb-8 rounded-[7px]">
                <Flex className="mb-3" align="center">
                  <Image
                    width={20}
                    className="w-[0.910625em] h-[0.9025em] mr-2"
                    src={throughput}
                    alt="Logo"
                  />
                  <div className="text-[#FFC442] font-medium text-sm">
                    Throughput
                  </div>
                </Flex>
                <Flex gap="6" className="mb-6" justify="between">
                  <Flex className="" align="center">
                    <div>
                      <Text_18_700_FFFFFF className="mb-1">
                        {benchmarkResult?.request_throughput}{" "}
                        <span className="font-bold text-xs ">requests/s</span>
                      </Text_18_700_FFFFFF>
                      <Text_10_400_FFFFFF>
                        Request throughput
                      </Text_10_400_FFFFFF>
                    </div>
                  </Flex>
                  <Flex className="" align="center">
                    <div>
                      <Text_18_700_FFFFFF className="mb-1">
                        {benchmarkResult?.input_throughput}{" "}
                        <span className="font-bold text-xs ">tokens/s</span>
                      </Text_18_700_FFFFFF>
                      <Text_10_400_FFFFFF>
                        Input token throughput
                      </Text_10_400_FFFFFF>
                    </div>
                  </Flex>
                  <Flex className="" align="center">
                    <div>
                      <Text_18_700_FFFFFF className="mb-1">
                        {benchmarkResult?.output_throughput}{" "}
                        <span className="font-bold text-xs ">tokens/s</span>
                      </Text_18_700_FFFFFF>
                      <Text_10_400_FFFFFF>
                        Output token throughput
                      </Text_10_400_FFFFFF>
                    </div>
                  </Flex>
                </Flex>
                <Flex gap="4" justify="between">
                  <Flex className="" align="center">
                    <div>
                      <Text_18_700_FFFFFF className="mb-1">
                        {benchmarkResult?.p25_throughput}
                        <span className="font-bold text-xs ml-1">
                          requests/s
                        </span>
                      </Text_18_700_FFFFFF>
                      <Text_10_400_FFFFFF>25 Percentile</Text_10_400_FFFFFF>
                    </div>
                  </Flex>
                  <Flex className="" align="center">
                    <div>
                      <Text_18_700_FFFFFF className="mb-1">
                        {benchmarkResult?.p75_throughput}
                        <span className="font-bold text-xs ml-1">
                          requests/s
                        </span>
                      </Text_18_700_FFFFFF>
                      <Text_10_400_FFFFFF>75 Percentile</Text_10_400_FFFFFF>
                    </div>
                  </Flex>
                  <Flex className="" align="center">
                    <div>
                      <Text_18_700_FFFFFF className="mb-1">
                        {benchmarkResult?.p95_throughput}
                        <span className="font-bold text-xs ml-1">
                          requests/s
                        </span>
                      </Text_18_700_FFFFFF>
                      <Text_10_400_FFFFFF>95 Percentile</Text_10_400_FFFFFF>
                    </div>
                  </Flex>
                  <Flex className="" align="center">
                    <div>
                      <Text_18_700_FFFFFF className="mb-1">
                        {benchmarkResult?.p99_throughput}
                        <span className="font-bold text-xs ml-1">
                          requests/s
                        </span>
                      </Text_18_700_FFFFFF>
                      <Text_10_400_FFFFFF>99 Percentile</Text_10_400_FFFFFF>
                    </div>
                  </Flex>
                </Flex>
              </Box>
            </Grid>
          </div>
          <Grid columns={{ initial: "1", md: "3" }} gap="3" width="auto">
            <Box className="bg-[#18191B] mt-4 px-5 py-4 rounded-[7px]">
              <div>
                <Flex className="mb-3" align="center">
                  <Image
                    width={20}
                    className="w-[1.15em] h-[1.15em] mr-2"
                    src={timeSettingIcon}
                    alt="Logo"
                  />
                  <div className="text-[#C64C9C] font-medium text-sm">TPOT</div>
                </Flex>
                <Flex gap="6" className="mb-6">
                  <Flex className="mr-6" align="center">
                    <div>
                      <Text_18_700_FFFFFF className="mb-1">
                        {benchmarkResult?.mean_tpot_ms}{" "}
                        <span className="font-bold text-xs ">ms</span>
                      </Text_18_700_FFFFFF>
                      <Text_8_400_FFFFFF>Mean TPOT</Text_8_400_FFFFFF>
                    </div>
                  </Flex>
                  <Flex className="" align="center">
                    <div>
                      <Text_18_700_FFFFFF className="mb-1">
                        {benchmarkResult?.median_tpot_ms}{" "}
                        <span className="font-bold text-xs ">ms</span>
                      </Text_18_700_FFFFFF>
                      <Text_8_400_FFFFFF>Median TPOT</Text_8_400_FFFFFF>
                    </div>
                  </Flex>
                </Flex>
              </div>
            </Box>
            <Box className="bg-[#18191B] mt-4 px-5 py-4 rounded-[7px]">
              <div>
                <Flex className="mb-3" align="center">
                  <Image
                    width={20}
                    className="w-[1.15em] h-[1.15em] mr-2"
                    src={cacheIcon}
                    alt="Logo"
                  />
                  <div className="text-[#D45453] font-medium text-sm">
                    Cache
                  </div>
                </Flex>
                <Flex gap="6" className="mb-6">
                  <Flex className="mr-6" align="center">
                    <div>
                      <Text_18_700_FFFFFF className="mb-1">
                        {benchmarkResult?.cache_hit}
                      </Text_18_700_FFFFFF>
                      <Text_8_400_FFFFFF>Number of Cache hit</Text_8_400_FFFFFF>
                    </div>
                  </Flex>
                  <Flex className="" align="center">
                    <div>
                      <Text_18_700_FFFFFF className="mb-1">
                        {benchmarkResult?.mean_cache_latency ? (
                          <>
                            {benchmarkResult?.mean_cache_latency}
                            <span className="font-bold text-xs ">ms</span>
                          </>
                        ) : (
                          "-"
                        )}{" "}
                      </Text_18_700_FFFFFF>
                      <Text_8_400_FFFFFF>Cache Latency</Text_8_400_FFFFFF>
                    </div>
                  </Flex>
                </Flex>
              </div>
            </Box>
            <Box className="bg-[#18191B] mt-4 px-5 py-4 rounded-[7px]">
              <div>
                <Flex className="mb-3" align="center">
                  <Image
                    width={20}
                    className="w-[1.14875em] h-[1.14875em] mr-2"
                    src={tokenIcon}
                    alt="Logo"
                  />
                  <div className="text-[#3F8EF7] font-medium text-sm">
                    Tokens
                  </div>
                </Flex>
                <Flex gap="6" className="mb-6">
                  <Flex className="mr-6" align="center">
                    <div>
                      <Text_18_700_FFFFFF className="mb-1">
                        {benchmarkResult?.total_input_tokens}
                      </Text_18_700_FFFFFF>
                      <Text_8_400_FFFFFF>Total input tokens</Text_8_400_FFFFFF>
                    </div>
                  </Flex>
                  <Flex className="" align="center">
                    <div>
                      <Text_18_700_FFFFFF className="mb-1">
                        {benchmarkResult?.total_output_tokens}
                      </Text_18_700_FFFFFF>
                      <Text_8_400_FFFFFF>Total output tokens</Text_8_400_FFFFFF>
                    </div>
                  </Flex>
                </Flex>
              </div>
            </Box>
          </Grid>
        </div>
      </div>
    </DashBoardLayout>
  );
};

export default BenchmarkHistory;
