import { Button, Image } from "antd";
import React, { useContext } from "react";
import SearchHeaderInput from "../components/input/SearchHeaderInput";
import { ModelListCard } from "../components/ModelListCard";
import BlurModal from "../components/modal/BlurModal";
import { useEndPoints } from "../hooks/useEndPoint";
import { ChevronDown, ChevronUp } from "lucide-react";
import ChatContext from "@/app/context/ChatContext";
import RootContext from "@/app/context/RootContext";
import { assetBaseUrl } from "../environment";
import { Text_12_400_EEEEEE } from "@/lib/text";

interface LoadModelProps {
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
}

function LoadModel(props: LoadModelProps) {
  const { endpoints } = useEndPoints();
  const [searchValue, setSearchValue] = React.useState("");
  const { chat } = useContext(ChatContext);
  const { handleDeploymentSelect, chats } = useContext(RootContext);
  const [sortBy, setSortBy] = React.useState("recency");
  const [sortOrder, setSortOrder] = React.useState("desc");

  React.useEffect(() => {
    document.documentElement.scrollTop = document.documentElement.clientHeight;
    document.documentElement.scrollLeft = document.documentElement.clientWidth;
  }, []);

  const currentlyLoaded = endpoints?.filter((endpoint) =>
    chats.find((chat) => chat.selectedDeployment?.id === endpoint.id)
  );
  const availableModels = endpoints?.filter((endpoint) =>
    chats.find((chat) => chat.selectedDeployment?.id !== endpoint.id)
  )?.sort((a, b) => {
    if (sortOrder === "asc") {
      return a.name.localeCompare(b.name);
    } else {
      return b.name.localeCompare(a.name);
    }
  }
  );

  return (
    <div>
      <BlurModal
        width="520px"
        height="400px"
        open={props.open}
        onClose={() => props.setOpen(false)}
      >
        <div className="BlurModal shadow-[0px_6px_10px_0px_#1F1F1F66] border-[1px] border-[#1F1F1FB3] rounded-[10px] overflow-hidden">
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
                  {currentlyLoaded?.length}
                </span>
              </div>
              <div className="text-[#757575] text-[0.625rem] font-[400]">
                Memory Consumption:
                <span className="text-[#FFF] text-[0.625rem] font-[400] ml-[0.25rem]">
                  4.59/16 GB
                </span>
              </div>
            </div>
            {currentlyLoaded?.map((endpoint) => (
              <ModelListCard
                key={endpoint.id}
                data={endpoint}
                selectable={chat?.selectedDeployment?.id === endpoint.id}
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
                  {availableModels?.length}
                </span>
              </div>
              <div className="flex items-center gap-x-[0.25rem] justify-between hover:text-[#FFF] cursor-pointer">
                <div
                  className="text-[#B3B3B3] text-[0.5rem] font-[400] flex items-center gap-x-[0.25rem] bg-[#1E1E1E] rounded-[6px] px-[0.5rem] py-[0.25rem] capitalize"
                  onClick={() =>
                    setSortOrder(sortOrder === "asc" ? "desc" : "asc")
                  }
                >
                  {sortBy}
                  {sortOrder === "asc" ? (
                    <ChevronUp
                      width={9}
                      height={9}
                      className="text-[#B3B3B3] cursor-pointer text-[0.6rem]"
                    />
                  ) : (
                    <ChevronDown
                      width={9}
                      height={9}
                      className="text-[#B3B3B3] cursor-pointer text-[0.6rem]"
                    />
                  )}
                </div>
                <span className="text-[#FFF] text-[0.5rem] font-[400] ml-[0.25rem]">
                  Size
                </span>
              </div>
            </div>
            {availableModels
              ?.filter(
                (endpoint) =>
                  !chat?.selectedDeployment ||
                  endpoint.id !== chat.selectedDeployment.id
              )
              ?.filter((endpoint) =>
                endpoint.name.toLowerCase().includes(searchValue.toLowerCase())
              )
              ?.map((endpoint) => (
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
          className="w-[12.25rem] 2rem border-[1px] border-[#1F1F1F]"
          onClick={() => props.setOpen(!props.open)}
        >
          <Image
            src={`${assetBaseUrl}/${chat.selectedDeployment?.model?.provider?.icon}`}
            preview={false}
            alt="bud"
            style={{
              width: ".875rem",
              height: ".875rem",
            }}
          />
          <Text_12_400_EEEEEE>{chat.selectedDeployment.name}</Text_12_400_EEEEEE>
        </Button>
      ) : (
        <Button
          type="primary"
          className=" w-[12.25rem] 2rem"
          onClick={() => props.setOpen(!props.open)}
        >
          <Text_12_400_EEEEEE>Load Model</Text_12_400_EEEEEE>
        </Button>
      )}
    </div>
  );
}

export default LoadModel;
