import React, { useEffect } from "react";

import history from "../../images/icons/history.svg";
import { Button, Image } from "antd";
import Health from "../../chart/Health";
import LoadModel from "../../chat/LoadModel";
import { Endpoint, useEndPoints } from "../../hooks/useEndPoint";
import LoadModelConfig from "../../chat/LoadModelConfig";

interface NavBarProps {
  onToggleLeftSidebar: () => void;
  onToggleRightSidebar: () => void;
  isLeftSidebarOpen: boolean;
  isRightSidebarOpen: boolean;
}

function NavBar({
  onToggleLeftSidebar,
  onToggleRightSidebar,
  isLeftSidebarOpen,
  isRightSidebarOpen,
}: NavBarProps) {
  const [open, setOpen] = React.useState(false);
  const [openEdit, setOpenEdit] = React.useState(false);

  console.log("open", open);
  console.log("openEdit", openEdit);

  const [selectedModel, setSelectedModel] = React.useState<Endpoint | null>(
    null
  );
  const { endPoints, getEndPoints } = useEndPoints();

  useEffect(() => {
    console.log("getEndPoints");
    getEndPoints({ page: 1, limit: 10 });
  }, [open]);

  return (
    <div className="topBg text-[#FFF] p-[1rem] flex justify-between items-center h-[3.625rem] relative sticky top-0  z-10 bg-[#101010] border-b-[1px] border-b-[#1F1F1F]">
      <button
        style={{
          display: isLeftSidebarOpen ? "none" : "block",
        }}
        className="flex items-center w-[1.475rem] height-[1.475rem] p-[.2rem] rounded-[6px] flex justify-center items-center hover:!bg-[#FFFFFF08] cursor-pointer"
        onClick={onToggleLeftSidebar}
      >
        <Image
          src={"/icons/history.svg"}
          width={"1.125rem"}
          height={"1.125rem"}
          alt="menu"
          preview={false}
        />
      </button>
      <div
        style={{
          display: isLeftSidebarOpen ? "block" : "none",
        }}
      />
      <LoadModel
        open={open}
        setOpen={setOpen}
        selected={selectedModel}
        setSelected={setSelectedModel}
        openEdit={openEdit}
        setOpenEdit={setOpenEdit}
      />
      <LoadModelConfig
        data={selectedModel}
        open={openEdit}
        setOpen={setOpenEdit}
      />
      <div className="flex items-center gap-[.5rem]">
        <button
          style={{
            display: isRightSidebarOpen ? "none" : "block",
          }}
          className="w-[1.475rem] height-[1.475rem] p-[.2rem] rounded-[6px] flex justify-center items-center hover:!bg-[#FFFFFF08] cursor-pointer"
          onClick={onToggleRightSidebar}
        >
          <Image
            src={"/icons/settings.svg"}
            width={"1.125rem"}
            height={"1.125rem"}
            alt="menu"
            preview={false}
          />
        </button>
        <button className="w-[1.475rem] height-[1.475rem] p-[.2rem] rounded-[6px] flex justify-center items-center hover:!bg-[#FFFFFF08] cursor-pointer">
          <Image
            src={"/icons/plus.svg"}
            width={"1.125rem"}
            height={"1.125rem"}
            alt="menu"
            preview={false}
          />
        </button>
        <button className="mr-[.4rem] w-[1.475rem] height-[1.475rem] p-[.2rem] rounded-[6px] flex justify-center items-center hover:!bg-[#FFFFFF08] cursor-pointer">
          <Image
            src={"/icons/more.svg"}
            width={"1.125rem"}
            height={"1.125rem"}
            alt="menu"
            preview={false}
          />
        </button>
      </div>
    </div>
  );
}

export default NavBar;
