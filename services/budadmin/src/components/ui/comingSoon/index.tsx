import React from "react";
import { Text_16_400_FFFFFF } from "../text";
import { Image } from "antd";

interface ComingSoonProps {
  textMessage?: any;
  classNames?: string;
  shrink?: boolean;
  scaleValue?: number;
  comingYpos?: any;
  comingXpos?: any;
  comingOverlay?: string;
}

const ComingSoon: React.FC<ComingSoonProps> = ({
  textMessage,
  classNames,
  shrink = false,
  scaleValue = 1,
  comingYpos = "0",
  comingXpos = "0",
  comingOverlay = "#141414",
}) => {
  return (
    <div className="absolute w-full h-full top-0 left-0 z-[1100] flex justify-center items-center">
      <div
        className={`absolute z-[1100] w-full h-full top-0 left-0 bg-[${comingOverlay}] opacity-[.7]`}
        style={{
          background: comingOverlay,
        }}
      ></div>
      <div
        className={`relative z-[1201] justify-center items-center px-[1rem] py-[.35rem] rounded-[6px] border border-[1px solid #1F1F1F] bg-[#161616] max-h-[2.1875rem]`}
        style={{
          marginTop: comingYpos,
          marginLeft: comingXpos,
          transform: shrink ? `scale(${scaleValue})` : "scale(1)", // Apply scaling
          transition: "transform 0.3s ease", // Smooth transition
        }}
      >
        <div className="w-[3rem] absolute right-[.1rem] top-[-2.1rem]">
          <Image
            preview={false}
            src="/images/nodataBud.png"
            className=""
            alt=""
            style={{ width: "3rem" }}
          />
        </div>
        <Text_16_400_FFFFFF className="leading-[115%]">
          {textMessage || "Coming Soon"}
        </Text_16_400_FFFFFF>
      </div>
    </div>
  );
};

export default ComingSoon;

// function ModelCard({
//   selected,
//   handleClick,
//   data,
// }: {
//   selected?: boolean;
//   handleClick?: () => void;
//   data: any,
// }) {
//   const [hover, setHover] = React.useState(false);

//   const {
//     icon,
//     name,
//     description,
//   } = data;

//   return (
//     <div
//       onMouseEnter={() => setHover(true)}
//       onClick={handleClick}
//       onMouseLeave={() => setHover(false)}
//       className="relative pt-[.6rem] pb-[.95rem] cursor-pointer hover:shadow-lg px-[1.5rem] border-y-[0.5px] border-y-[#1F1F1F] hover:border-y-[#757575] flex-row flex items-center border-box hover:bg-[#FFFFFF08]"
//     >
//       {name == 'URL' && (
//         <ComingSoon />
//       )}
//       {name == 'Disk' && (
//         <ComingSoon />
//       )}
//       <div className="bg-[#1F1F1F] rounded-[4px] w-[1.75rem] h-[1.75rem] flex justify-center items-center mr-[.8rem] grow-0 shrink-0">
//         <div className=" w-[0.875rem] h-[0.875rem]" >
//           <Image
//             preview={false}
//             // src="/images/drawer/zephyr.png"
//             src={icon}
//             alt="info"
//             style={{width: '0.875rem', height: '0.875rem'}}
//           />
//         </div>
//       </div>
//       <div className="flex justify-between w-full flex-col">
//         <div className="flex items-center justify-between h-4">
//           <div className="flex pt-[.4rem]">
//             <Text_14_400_EEEEEE className="mr-2 truncate leading-[2rem]"
//             > {name} </Text_14_400_EEEEEE>
//           </div>
//         </div>
//         <Text_12_400_757575 className="text-[#757575] w-full overflow-hidden text-ellipsis pt-[.6rem] text-xs leading-[1.3rem]">
//           {description}
//         </Text_12_400_757575>
//       </div>
//       <div
//         style={{
//           display: hover || selected ? "flex" : "none",
//         }}
//         className="justify-end items-center"
//       >
//         <Checkbox checked={selected} className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]" />
//       </div>
//     </div>
//   );
// }
