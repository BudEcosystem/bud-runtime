import React, { useContext, useState } from "react";

import { Image } from 'antd';
import { Text_18_500_EEEEEE } from "../../text";


const NewProjectCardData: React.FC = (props: {

}) => {

  return (
    <div className="px-[1.4rem] py-[1.4rem]">
      <div className="flex justify-start items-center">
        <div className="w-[2.25rem] h-[2.25rem] rounded-[4px] bg-[#35341B] flex justify-center items-center mr-[1rem]">
          <Image
            width={24}
            height={24}
            src="/images/gift.png"
            alt=""
          />
        </div>
        <Text_18_500_EEEEEE>Bud test project </Text_18_500_EEEEEE>
      </div>
      <div className="flex items-center justify-start gap-[.5rem] mt-[1.4rem]">
        <div className="text-[#EC7575] text-[.75rem] leading-[100%] font-[400] p-[.5rem] rounded-[6px] bg-[#861A1A33]">Development</div>
        <div className="text-[#D1B854] text-[.75rem] leading-[100%] font-[400] p-[.5rem] rounded-[6px] bg-[#423A1A40]">Testing</div> 
      </div>
    </div>
  );
};

export default NewProjectCardData;
