"use client";
import ComingSoon from "@/components/ui/comingSoon";
import DashBoardLayout from "../layout";
import {
  Text_12_400_6A6E76,
  Text_16_600_FFFFFF,
  Text_18_500_EEEEEE,
} from "@/components/ui/text";

export default function Help() {
  return (
    <DashBoardLayout>
      <div className="boardPageView flex justify-center items-center">
        <ComingSoon shrink={true} scaleValue={.9} comingYpos='0%'/>
      </div>
    </DashBoardLayout>
  );
}
