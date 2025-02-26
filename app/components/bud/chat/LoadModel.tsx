import { Button, Image } from "antd";
import React, { useContext } from "react";
import SearchHeaderInput from "../components/input/SearchHeaderInput";
import { ModelListCard } from "../components/ModelListCard";
import BlurModal from "../components/modal/BlurModal";
import { useEndPoints } from "../hooks/useEndPoint";
import { ChevronUp } from "lucide-react";
import ChatContext from "@/app/context/ChatContext";
import RootContext from "@/app/context/RootContext";
import { assetBaseUrl } from "../environment";

interface LoadModelProps {
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
}

function LoadModel(props: LoadModelProps) {
  const { endpoints } = useEndPoints();
  const [searchValue, setSearchValue] = React.useState("");
  const { chat } = useContext(ChatContext);
  const { handleDeploymentSelect } = useContext(RootContext);

  React.useEffect(() => {
    document.documentElement.scrollTop = document.documentElement.clientHeight;
    document.documentElement.scrollLeft = document.documentElement.clientWidth;
  }, []);

  return (
    <div>
      <BlurModal
        width="520px"
        height="400px"
        open={props.open}
        onClose={() => props.setOpen(false)}
      >
        <div>
          <div className="p-[1.25rem]">
            <SearchHeaderInput
              searchValue={searchValue}
              setSearchValue={setSearchValue}
              classNames="w-full h-[28px] bg-[#1E1E1E] border-[1px] border-[#3A3A3A] border-solid rounded-[4px] !text-[#FFF] pl-[1rem] !text-[.75rem] font-[400]"
              expanded
              placeholder="Model names, Tags, Tasks, Parameter sizes"
            />
          </div>
          <div className="w-full  overflow-y-auto scrollbar-thin scrollbar-thumb-[#757575] scrollbar-track-[#1E1E1E] scrollbar-thumb-rounded-full scrollbar-track-rounded-full">
            <div className="flex justify-between items-center px-[1.25rem] py-[0.625rem]">
              <div className="text-[#757575] text-[0.75rem] font-[400]">
                Currently Loaded
                <span className="text-[#FFF] text-[0.75rem] font-[400] ml-[0.25rem]">
                  {endpoints.length}
                </span>
              </div>
              <div className="text-[#757575] text-[0.625rem] font-[400]">
                Memory Consumption:
                <span className="text-[#FFF] text-[0.625rem] font-[400] ml-[0.25rem]">
                  4.59/16 GB
                </span>
              </div>
            </div>
            {endpoints.map((endpoint) => (
              <ModelListCard
                key={endpoint.id}
                data={endpoint}
                selectable
                selected={chat?.selectedDeployment?.id === endpoint.id}
                handleClick={() => {
                  if (chat) {
                    handleDeploymentSelect(chat, endpoint);
                    props.setOpen(false);
                  }
                }}
              />
            ))}
          </div>
          <div className="w-full h-[320px] overflow-y-auto scrollbar-thin scrollbar-thumb-[#757575] scrollbar-track-[#1E1E1E] scrollbar-thumb-rounded-full scrollbar-track-rounded-full">
            <div className="flex justify-between items-center px-[1.25rem] py-[0.625rem]">
              <div className="text-[#757575] text-[0.75rem] font-[400]">
                Models Available
                <span className="text-[#FFF] text-[0.75rem] font-[400] ml-[0.25rem]">
                  {endpoints.length}
                </span>
              </div>
              <div className="flex items-center gap-x-[0.25rem] justify-between">
                <div className="text-[#B3B3B3] text-[0.5rem] font-[400] flex items-center gap-x-[0.25rem] bg-[#1E1E1E] rounded-[6px] px-[0.5rem] py-[0.25rem]">
                  Recency
                  <ChevronUp
                    width={9}
                    height={9}
                    className="text-[#B3B3B3] cursor-pointer text-[0.6rem]"
                  />
                </div>
                <span className="text-[#FFF] text-[0.5rem] font-[400] ml-[0.25rem]">
                  Size
                </span>
              </div>
            </div>
            {endpoints.map((endpoint) => (
              <ModelListCard
                key={endpoint.id}
                data={endpoint}
                handleClick={() => {
                  if (chat) {
                    handleDeploymentSelect(chat, endpoint);
                    props.setOpen(false);
                  }
                }}
              />
            ))}
          </div>
        </div>
      </BlurModal>
      {chat?.selectedDeployment ? (
        <Button
          type="default"
          className="text-[#FFF] w-[196px] h-[32px]"
          onClick={() => props.setOpen(!props.open)}
        >
          <Image
            src={`${assetBaseUrl}/${chat.selectedDeployment?.model?.provider?.icon}`}
            preview={false}
            alt="bud"
            width={"0.625rem"}
            height={"0.625rem"}
          />
          {chat.selectedDeployment.name}
        </Button>
      ) : (
        <Button
          type="primary"
          className="text-[#FFF] w-[196px] h-[32px]"
          onClick={() => props.setOpen(!props.open)}
        >
          Load Model
        </Button>
      )}
    </div>
  );
}

export default LoadModel;
