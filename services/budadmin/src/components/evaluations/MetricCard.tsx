import React from "react";
import { 
  Text_16_600_FFFFFF, 
  Text_12_400_B3B3B3, 
  Text_24_600_FFFFFF, 
  Text_32_600_FFFFFF,
  Text_18_400_EEEEEE,
  Text_10_400_B3B3B3
} from "@/components/ui/text";

interface MetricCardProps {
  title: string;
  value: string;
  subtitle: string;
  color: string;
}

const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  color,
}) => {
  return (
    <div className="bg-[#101010] rounded-lg p-[1.5rem] border border-[#1F1F1F] hover:border-[#2A2A2A] transition-colors">
      <div className="flex flex-col space-y-2 pt-[.4rem] pb-[.4rem] justify-center items-center">
        <Text_18_400_EEEEEE className="pb-[.7rem]">{title}</Text_18_400_EEEEEE>
        <div className="flex flex-col items-center justify-center space-x-2">
          <Text_32_600_FFFFFF className={`text-[${color}]`}>{value}</Text_32_600_FFFFFF>
          <Text_10_400_B3B3B3 className="pt-[.5rem]">{subtitle}</Text_10_400_B3B3B3>
        </div>
      </div>
    </div>
  );
};

export default MetricCard;