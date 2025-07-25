import React from "react";
import { Flex, Grid, Image, Typography, Segmented, Carousel } from 'antd';
import { Heading_26_600_FFFFFF, Text_13_400_757575, Text_13_400_B3B3B3 } from "../text";
import noAccessIcn from "./../../../../public/icons/noaccess.png";
import Tags from "src/flows/components/DrawerTags";

interface noAccessProps {
  textMessage?: any,
  classNames?: string
  classNamesInner?: string
  classNamesInnerTwo?: string
  image?: string
}
const NoChartData: React.FC<noAccessProps> = ({ textMessage, classNames, image, classNamesInner, classNamesInnerTwo}) => {

  return (
    <div className={`${classNames}`}>
      <div className=" flex flex-col items-start">
        <div className="flex rounded-md items-center mb-[.1rem] ">
          <Text_13_400_757575 className="py-[.8rem] pb-[.6rem] leading-[120%]">{textMessage}</Text_13_400_757575>
        </div>
        <p className="text-[1.625rem] text-[#EEEEEE] leading-[100%] font-[400] mb-[.3rem]">--</p>
        <Tags name="Not available" classNames="w-fit"  color="#757575" />
      </div>
      <div className={`mt-[1.95rem] ${classNamesInner}`}
      style={{
        height: "172px"
      }}
      >
        <div className={`flex justify-center	items-cente rounded-md bg-[#1F1F1F] ${classNamesInnerTwo}`}
        style={{
          height: "135px"
        }}
        >
          <div className="text-center	flex items-center flex-col justify-center">
            <div className="text-center	">
              <Image
                preview={false}
                width={43}
                src={image}
                className="ml-[.2rem]"
                alt=""
              />
            </div>
            <Text_13_400_B3B3B3>No data available</Text_13_400_B3B3B3>
          </div>
        </div>
      </div>
    </div>
  );
};

export default NoChartData;
