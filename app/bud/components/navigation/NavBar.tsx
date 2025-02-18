import React from "react";

import history from "../../images/icons/history.svg";
import { Button, Image } from "antd";
import Health from "../../chart/Health";
import LoadModel from "../LoadModel";

function NavBar() {
  const healthCards = [
    {
      title: "RAM",
    },
    {
      title: "CPU",
    },
  ];

  return (
    <div className=" text-[#FFF] p-[1rem] flex justify-between items-center h-[58px] relative sticky top-0  z-10 bg-[#101010]">
      <div className="blur-[0.5rem] absolute top-0 left-0 right-0 bottom-0 bg-[#FFFFFF03] rounded-[0.5rem]" />
      <button className="flex items-center">
        <Image
          src={"/icons/history.svg"}
          width={"1.125rem"}
          height={"1.125rem"}
          alt="menu"
          preview={false}
        />
      </button>
      <LoadModel />
      <div className="flex items-center gap-[1rem]">
        <div className="flex items-center gap-[1rem]">
          {healthCards.map((card) => (
            <div className="flex items-center gap-[0.5rem]  p-[0.5rem] rounded-[0.5rem] relative">
              <div className="blur-[0.5rem] absolute top-0 left-0 right-0 bottom-0 bg-[#FFFFFF03] rounded-[0.5rem]"></div>
              <div className="text-[#FFF] text-[0.625rem] font-bold">
                {card.title}:
              </div>
              <Health />
            </div>
          ))}
        </div>
        <button>
          <Image
            src={"/icons/settings.svg"}
            width={"1.125rem"}
            height={"1.125rem"}
            alt="menu"
            preview={false}
          />
        </button>
        <button>
          <Image
            src={"/icons/plus.svg"}
            width={"1.125rem"}
            height={"1.125rem"}
            alt="menu"
            preview={false}
          />
        </button>
        <button>
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
