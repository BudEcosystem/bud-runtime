import { Text_12_400_B3B3B3, Text_12_400_EEEEEE } from "@/components/ui/text";
import { Image } from "antd";

type Props = {
  estimatedTime: string;
};

export function StatusEstimatedTime(props: Props) {
  return (
    <div className="flex flex-start! items-center! w-full px-[1.35rem] justify-start">
      <div className="flex justify-center items-center px-[.8rem] py-[.4rem] rounded-[21px] bg-[#1F1F1F]">
        <div className="w-[1rem] h-[1rem] mr-[.4rem]">
          <Image
            preview={false}
            src="/images/drawer/clock.png"
            alt="info"
            style={{ width: "1rem", height: "1rem", marginRight: ".4rem" }}
          />
        </div>
        {props.estimatedTime ? (
          <Text_12_400_B3B3B3 className="leading-[100%] whitespace-nowrap">
            Estimated Time
          </Text_12_400_B3B3B3>
        ) : (
          <Text_12_400_B3B3B3 className="leading-[100%] whitespace-nowrap">
            Calculating <span className="animate-pulse">...</span>
          </Text_12_400_B3B3B3>
        )}
        <Text_12_400_EEEEEE className="leading-[100%] ml-[.3rem] whitespace-nowrap">
          {props.estimatedTime}
        </Text_12_400_EEEEEE>
      </div>
    </div>
  );
}
