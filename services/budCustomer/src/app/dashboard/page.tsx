"use client";
import React, { useState, useEffect } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { Flex, Image, Carousel } from "antd";
import {
  Text_12_400_757575,
  Text_13_400_479D5F,
  Text_13_400_EC7575,
  Text_13_400_4077E6,
  Text_13_400_965CDE,
  Text_13_400_D1B854,
  Text_14_400_EEEEEE,
  Text_15_600_EEEEEE,
  Text_19_600_EEEEEE,
  Text_26_400_EEEEEE,
  Text_38_400_EEEEEE,
  Text_53_400_EEEEEE
} from "@/components/ui/text";
import styles from "./dashboard.module.scss";

export default function DashboardPage() {
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  if (!isMounted) {
    return null;
  }

  return (
    <DashboardLayout>
      <div className="w-full h-full overflow-y-auto">
        <div className="p-8">
          {/* Main Grid Layout */}
          <div className="grid grid-cols-12 gap-6">
            {/* Savings Card - Purple Gradient Background */}
            <div className="col-span-5 relative overflow-hidden rounded-lg border border-[#1F1F1F] bg-gradient-to-br from-[#472A9B] to-[#2011CB] p-8">
              <div className="relative z-10">
                <Text_53_400_EEEEEE>89 %</Text_53_400_EEEEEE>
                <Flex className="items-center gap-2 mt-2">
                  <Text_13_400_479D5F>Savings</Text_13_400_479D5F>
                  <Image
                    preview={false}
                    width={15}
                    src="/images/dashboard/greenArrow.png"
                    alt=""
                  />
                </Flex>
                <div className="mt-8">
                  <Text_15_600_EEEEEE>
                    Increase in your revenue
                    <span className="font-normal text-[#757575]"> by end of this month is forecasted.</span>
                  </Text_15_600_EEEEEE>
                  <p className="text-[13px] text-[#757575] mt-4">
                    Harver is about to receive 15k new customers which results in 78% increase in revenue
                  </p>
                </div>
              </div>
              {/* Gradient overlay */}
              <div className="absolute inset-0 bg-gradient-to-br from-transparent via-[#965CDE20] to-transparent" />
            </div>

            {/* Total Requests Card */}
            <div className="col-span-4 border border-[#1F1F1F] rounded-lg bg-[#0A0A0A] p-6">
              <div className="mb-4">
                <Text_15_600_EEEEEE>Total Requests</Text_15_600_EEEEEE>
                <div className="h-[3px] w-7 bg-[#965CDE] mt-1" />
              </div>
              <Flex className="items-end gap-2">
                <Text_38_400_EEEEEE>1</Text_38_400_EEEEEE>
                <Flex className="items-center gap-1 mb-2 bg-[#861A1A33] px-2 py-1 rounded">
                  <Image
                    preview={false}
                    width={12}
                    src="/images/dashboard/down.png"
                    alt=""
                  />
                  <span className="text-[#EC7575] text-xs">-50.00%</span>
                </Flex>
              </Flex>
              <Text_12_400_757575>Last 7 days</Text_12_400_757575>
              {/* Simple line chart representation */}
              <div className="mt-4 h-20 flex items-end justify-between gap-1">
                {[20, 40, 80, 60, 70, 50, 30].map((height, i) => (
                  <div key={i} className="flex-1 bg-[#965CDE40]" style={{ height: `${height}%` }} />
                ))}
              </div>
            </div>

            {/* Models Card */}
            <div className="col-span-3 border border-[#1F1F1F] rounded-lg bg-[#0A0A0A] p-6">
              <div className="mb-4">
                <Text_15_600_EEEEEE>Models</Text_15_600_EEEEEE>
                <div className="h-[3px] w-7 bg-[#965CDE] mt-1" />
              </div>
              <Text_38_400_EEEEEE>65</Text_38_400_EEEEEE>
              <Flex className="gap-2 mt-3">
                <Flex className="items-center gap-1 bg-[#8F55D62B] px-2 py-1 rounded">
                  <Image
                    preview={false}
                    width={13}
                    src="/images/dashboard/purpleCloud.png"
                    alt=""
                  />
                  <Text_13_400_965CDE>1 Cloud</Text_13_400_965CDE>
                </Flex>
                <Flex className="items-center gap-1 bg-[#423A1A40] px-2 py-1 rounded">
                  <Image
                    preview={false}
                    width={13}
                    src="/images/dashboard/hug.png"
                    alt=""
                  />
                  <Text_13_400_D1B854>64 Local</Text_13_400_D1B854>
                </Flex>
              </Flex>
            </div>

            {/* Second Row - Stat Cards */}
            {/* Endpoints Card */}
            <div className="col-span-4 border border-[#1F1F1F] rounded-lg bg-[#0A0A0A] p-6 relative overflow-hidden">
              <Image
                preview={false}
                src="/images/dashboard/mask2.png"
                className="absolute top-0 right-0 opacity-20"
                alt=""
              />
              <div className="relative z-10">
                <Text_15_600_EEEEEE>Endpoints</Text_15_600_EEEEEE>
                <Text_38_400_EEEEEE className="mt-4">1</Text_38_400_EEEEEE>
                <Flex className="items-center gap-1 bg-[#122F1140] px-2 py-1 rounded w-fit mt-2">
                  <Text_13_400_479D5F>1 Running</Text_13_400_479D5F>
                </Flex>
              </div>
            </div>

            {/* Clusters Card */}
            <div className="col-span-4 border border-[#1F1F1F] rounded-lg bg-[#0A0A0A] p-6 relative overflow-hidden">
              <Image
                preview={false}
                src="/images/dashboard/mask3.png"
                className="absolute top-0 right-0 opacity-20"
                alt=""
              />
              <div className="relative z-10">
                <Text_15_600_EEEEEE>Clusters</Text_15_600_EEEEEE>
                <Text_38_400_EEEEEE className="mt-4">6</Text_38_400_EEEEEE>
                <Flex className="items-center gap-1 bg-[#861A1A33] px-2 py-1 rounded w-fit mt-2">
                  <Text_13_400_EC7575>5 Not Available</Text_13_400_EC7575>
                </Flex>
              </div>
            </div>

            {/* Projects Card */}
            <div className="col-span-4 border border-[#1F1F1F] rounded-lg bg-[#0A0A0A] p-6 relative overflow-hidden">
              <Image
                preview={false}
                src="/images/dashboard/mask4.png"
                className="absolute top-0 right-0 opacity-20"
                alt=""
              />
              <div className="relative z-10">
                <Text_15_600_EEEEEE>Projects</Text_15_600_EEEEEE>
                <Text_38_400_EEEEEE className="mt-4">5</Text_38_400_EEEEEE>
                <Flex className="items-center gap-1 bg-[#1B325140] px-2 py-1 rounded w-fit mt-2">
                  <Text_13_400_4077E6>5 Members</Text_13_400_4077E6>
                </Flex>
              </div>
            </div>

            {/* Third Row - Metrics */}
            {/* Number of API Calls */}
            <div className="col-span-6 border border-[#1F1F1F] rounded-lg bg-[#0A0A0A] p-6">
              <Flex className="justify-between items-center mb-6">
                <Text_19_600_EEEEEE>Number of API Calls</Text_19_600_EEEEEE>
                <Flex className="gap-1">
                  <button className="px-3 py-1 text-xs border border-[#1F1F1F] rounded text-[#757575] hover:text-white hover:border-[#965CDE]">
                    LAST 24 HRS
                  </button>
                  <button className="px-3 py-1 text-xs border border-[#965CDE] rounded text-white bg-[#965CDE20]">
                    LAST 7 DAYS
                  </button>
                  <button className="px-3 py-1 text-xs border border-[#1F1F1F] rounded text-[#757575] hover:text-white hover:border-[#965CDE]">
                    LAST 30 DAYS
                  </button>
                </Flex>
              </Flex>
              <Text_26_400_EEEEEE>3.00</Text_26_400_EEEEEE>
              <Flex className="items-center gap-1 mt-2">
                <span className="text-[#479D5F] text-sm">Avg. 0.00%</span>
                <Image
                  preview={false}
                  width={12}
                  src="/images/dashboard/greenArrow.png"
                  alt=""
                />
              </Flex>
            </div>

            {/* Latency */}
            <div className="col-span-6 border border-[#1F1F1F] rounded-lg bg-[#0A0A0A] p-6">
              <Flex className="justify-between items-center mb-6">
                <Text_19_600_EEEEEE>Latency</Text_19_600_EEEEEE>
                <Flex className="gap-1">
                  <button className="px-3 py-1 text-xs border border-[#1F1F1F] rounded text-[#757575] hover:text-white hover:border-[#965CDE]">
                    LAST 24 HRS
                  </button>
                  <button className="px-3 py-1 text-xs border border-[#965CDE] rounded text-white bg-[#965CDE20]">
                    LAST 7 DAYS
                  </button>
                  <button className="px-3 py-1 text-xs border border-[#1F1F1F] rounded text-[#757575] hover:text-white hover:border-[#965CDE]">
                    LAST 30 DAYS
                  </button>
                </Flex>
              </Flex>
              <Text_26_400_EEEEEE>1351.67 ms</Text_26_400_EEEEEE>
              <Flex className="items-center gap-1 mt-2">
                <span className="text-[#479D5F] text-sm">Avg. 0.00%</span>
                <Image
                  preview={false}
                  width={12}
                  src="/images/dashboard/greenArrow.png"
                  alt=""
                />
              </Flex>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}