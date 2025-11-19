import { Button, Image } from "antd";
import React, { useEffect, useRef } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { assetBaseUrl } from "@/app/lib/environment";
import SearchHeaderInput from "../../components/bud/components/input/SearchHeaderInput";
import { ModelListCard } from "../../components/bud/components/ModelListCard";
import BlurModal from "../../components/bud/components/modal/BlurModal";
import { useEndPoints } from "@/app/components/bud/hooks/useEndPoint";
import { useChatStore } from "@/app/store/chat";
import { Text_12_400_EEEEEE } from "@/lib/text";

interface LoadModelProps {
    chatId: string;
    open: boolean;
    setOpen: React.Dispatch<React.SetStateAction<boolean>>;
}


export default function LoadModel(props: LoadModelProps) {
    const { endpoints, getEndPoints, isReady } = useEndPoints();
    const chat = useChatStore.getState().getChat(props.chatId);
    const { setDeployment, isDeploymentLocked } = useChatStore();
    const isLocked = isDeploymentLocked(props.chatId);

    const [sortBy, setSortBy] = React.useState("recency");
    const [sortOrder, setSortOrder] = React.useState("desc");
    const [currentlyLoaded, setCurrentlyLoaded] = React.useState<any[]>([]);
    const [availableModels, setAvailableModels] = React.useState<any[]>([]);
    const [searchValue, setSearchValue] = React.useState("");

    const containerRef = useRef<HTMLDivElement>(null);

    React.useEffect(() => {
        document.documentElement.scrollTop = document.documentElement.clientHeight;
        document.documentElement.scrollLeft = document.documentElement.clientWidth;
    }, []);

    useEffect(() => {
        if (props.open && isReady) {
            getEndPoints({ page: 1, limit: 25 });
        }
    }, [props.open, isReady, getEndPoints]);

    useEffect(() => {

        setCurrentlyLoaded(endpoints?.filter((endpoint) => chat?.selectedDeployment?.id === endpoint.id));
        setAvailableModels(endpoints?.filter((endpoint) =>
          chat?.selectedDeployment?.id !== endpoint.id
        )?.sort((a, b) => {
            if (sortOrder === "asc") {
              return a.name.localeCompare(b.name);
            } else {
              return b.name.localeCompare(a.name);
            }
          }
        ));
      }, [endpoints, chat, sortOrder]);


    return (
        <div ref={containerRef}>
            <BlurModal
                width="520px"
                height="400px"
                open={props.open && !isLocked}
                onClose={() => props.setOpen(false)}
                ref={containerRef}
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
                            {/* <div className="text-[#757575] text-[0.75rem] font-[400]">
                                Currently Loaded
                                <span className="text-[#FFF] text-[0.75rem] font-[400] ml-[0.25rem]">
                                    {currentlyLoaded?.length}
                                </span>
                            </div> */}
                            {/* <div className="text-[#757575] text-[0.625rem] font-[400]">
                    Memory Consumption:
                    <span className="text-[#FFF] text-[0.625rem] font-[400] ml-[0.25rem]">
                      4.59/16 GB
                    </span>
                  </div> */}
                        </div>
                        {currentlyLoaded?.map((endpoint) => (
                            <ModelListCard
                                key={endpoint.id}
                                data={endpoint}
                                selectable={chat?.selectedDeployment?.id === endpoint.id}
                                selected={chat?.selectedDeployment?.id === endpoint.id}
                                handleClick={() => {
                                    if (chat) {
                                        setDeployment(chat.id, endpoint);
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
                                    {endpoints?.length}
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
                                {/* <span className="text-[#FFF] text-[0.5rem] font-[400] ml-[0.25rem]">
                                    Size
                                </span> */}
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
                                            setDeployment(chat.id, endpoint);
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
                    className={`w-[12.25rem] 2rem border-[1px] border-[#1F1F1F] ${isLocked ? 'cursor-not-allowed opacity-75' : ''}`}
                    onClick={() => {
                        if (!isLocked) {
                            props.setOpen(!props.open);
                        }
                    }}
                    disabled={isLocked}
                    title={isLocked ? 'Model selection locked by prompt configuration' : 'Change model'}
                >
                    <Image
                        src={typeof chat.selectedDeployment.model === 'string'
                            ? "/icons/modelRepoWhite.png"
                            : `${assetBaseUrl}${chat.selectedDeployment.model?.icon || chat.selectedDeployment.model?.provider?.icon}`}
                        fallback={"/icons/modelRepoWhite.png"}
                        preview={false}
                        alt="bud"
                        style={{
                            width: ".875rem",
                            height: ".875rem",
                        }}
                    />
                    <Text_12_400_EEEEEE className="Open-Sans">
                        {chat.selectedDeployment.name}
                    </Text_12_400_EEEEEE>
                </Button>
            ) : (
                <Button
                    type="primary"
                    className=" w-[12.25rem] 2rem"
                    onClick={() => props.setOpen(!props.open)}
                >
                    <Text_12_400_EEEEEE className="Open-Sans">Load Model</Text_12_400_EEEEEE>
                </Button>
            )}
        </div>
    );
}
