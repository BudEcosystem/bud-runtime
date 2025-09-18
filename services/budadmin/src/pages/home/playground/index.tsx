"use client";
import DashBoardLayout from "../layout";
import dynamic from "next/dynamic";
import {
  Text_12_400_6A6E76,
  Text_16_600_FFFFFF,
  Text_18_500_EEEEEE,
} from "@/components/ui/text";
// import EmbeddedIframe from "./iFrame";

const EmbeddedIframe = dynamic(() => import("./iFrame"), { ssr: false });

export default function Help() {
  return (
    <DashBoardLayout>
      <div className="boardPageView flex justify-center items-center">
        <EmbeddedIframe />
      </div>
    </DashBoardLayout>
  );
}
