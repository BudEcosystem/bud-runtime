"use client";
import { useState } from "react";
import { Image } from "antd";

import { Text_12_400_B3B3B3 } from "@/components/ui/text";

import { useRouter } from "next/router";
import { Cluster } from "src/hooks/useCluster";
import Tags from "src/flows/components/DrawerTags";

interface GeneralProps {
  data: Cluster;
}


const HealthStatus: React.FC<GeneralProps> = ({ data }) => {
  const router = useRouter();
  const LogContent = [
    {
      time: '02:01:15',
      text: 'agent Submitted for execution: PID: 27446'
    },
    {
      time: '02:01:15',
      text: 'prefect.GitHub Downloading flow GitHub storage - repo : ‘ examples/conditional.py’, ref: ‘d44b2a950ebda9f7bca9712'
    },
    {
      time: '02:01:15',
      text: 'agent Submitted for execution: PID: 27446'
    },
    {
      time: '02:01:15',
      text: 'agent Submitted for execution: PID: 27446'
    },
  ]

  function Log({ item }: { item: any }) {
    const [isExpanded, setIsExpanded] = useState(false);

    return (
      <div
        className={`flex flex-col justify-start items-center px-[.5rem] rounded-[8px] bg-[#FFFFFF08] transition-all duration-300 py-[.95rem] ${isExpanded ? "h-auto" : "h-[2.8rem]"
          }`}
      >
        <div className="flex justify-start items-start w-full cursor-pointer"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          <div className={`w-[.9rem] h-[0.9rem] ml-[.5rem] mr-[.95rem] transition-transform origin-center duration-300 ${isExpanded ? "rotate-[180deg]" : "rotate-90"
            }`}
          >
            <Image
              preview={false}
              style={{ width: "0.9rem", height: "0.9rem" }}
              src="/images/drawer/ChevronUp.png"
              alt=""
            />
          </div>
          <div className="flex justify-start items-start max-w-[90%]">
            <Text_12_400_B3B3B3 className="mr-[1rem] leading-[1rem]">{item.time}</Text_12_400_B3B3B3>
            <div
              className={`ibm text-[#EEEEEE] font-[500] text-[.75rem] leading-[1rem] overflow-hidden ${isExpanded ? "whitespace-normal" : "text-nowrap"
                }`}
            >
              {item.text}
            </div>
          </div>

        </div>
      </div>
    );
  }

  return (
    <div className="w-full ">
      <div className="flex flex-col justify-start gap-[.9rem]">
        <div className="flex justify-start items-center">
          <div className="flex justify-start items-center px-[.15rem] w-[6.15rem]">
            <div className="w-[.75rem] mr-[.4rem]">
              <Image
                src="/images/drawer/meter.png"
                preview={false}
                alt="info"
                style={{ width: '.75rem', height: '.75rem' }}
              />
            </div>
            <Text_12_400_B3B3B3>Status</Text_12_400_B3B3B3>
          </div>
          <div>
            <Tags
              name="Critical"
              color="#EC7575"
            />
          </div>
        </div>
        <div className="flex justify-start items-center">
          <div className="flex justify-start items-center px-[.15rem] w-[6.15rem]">
            <div className="w-[.75rem] mr-[.4rem]">
              <Image
                src="/images/drawer/meter.png"
                preview={false}
                alt="info"
                style={{ width: '.75rem', height: '.75rem' }}
              />
            </div>
            <Text_12_400_B3B3B3>Activity</Text_12_400_B3B3B3>
          </div>
          <div>
            <Tags
              name="9 Warning messages"
              color="#EC7575"
            />
          </div>
        </div>
      </div>
      <div className="mt-[1.1rem] flex flex-col gap-[.8rem]">
        {LogContent.map((item, index) => (
          <Log key={index} item={item} />
        ))}
      </div>
    </div>
  );
};

export default HealthStatus;
