import React, { useContext } from "react";

import { Image, Tooltip } from "antd";
import LoadModel from "../../chat/LoadModel";
import ChatContext, { Endpoint } from "@/app/context/ChatContext";
import RootContext from "@/app/context/RootContext";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useMessages } from "../../hooks/useMessages";

interface NavBarProps {
  onToggleLeftSidebar: () => void;
  onToggleRightSidebar: () => void;
  isLeftSidebarOpen: boolean;
  isRightSidebarOpen: boolean;
  setChatData: (data: any) => void;
}

function NavBar({
  onToggleLeftSidebar,
  onToggleRightSidebar,
  isLeftSidebarOpen,
  isRightSidebarOpen,
  setChatData,
}: NavBarProps) {
  const [openDropdown, setOpenDropdown] = React.useState(false);
  const { createChat, closeChat } = useContext(RootContext);
  const { chat, setMessages } = useContext(ChatContext);
  const [open, setOpen] = React.useState(false);
  const { deleteSession } = useMessages();

  return (
    <div className="topBg text-[#FFF] p-[1rem] flex justify-between items-center h-[3.625rem] relative sticky top-0  z-10 bg-[#101010] border-b-[1px] border-b-[#1F1F1F]">
      {/* <div className="topBg text-[#FFF] p-[1rem] flex justify-between items-center h-[3.625rem] relative sticky top-0  z-10 bg-[#101010] border-b-[1px] border-b-[#1F1F1F]"> */}
      <button
        style={{
          display: isLeftSidebarOpen ? "none" : "block",
        }}
        className="flex items-center w-[1.475rem] height-[1.475rem] p-[.2rem] rounded-[6px] flex justify-center items-center cursor-pointer w-[95px]"
        onClick={onToggleLeftSidebar}
      >
        <div className="w-[1.125rem] h-[1.125rem] flex justify-center items-center cursor-pointer group text-[#B3B3B3] hover:text-[#FFFFFF]">
        <Tooltip title="Chat history">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="18"
            height="18"
            fill="none"
          >
            <path
              fill="currentColor"
              d="M9 1.688a7.32 7.32 0 0 0-6.188 3.42v-1.17a.562.562 0 1 0-1.124 0V6.75a.563.563 0 0 0 .562.563h2.812a.562.562 0 1 0 0-1.125H3.495a6.184 6.184 0 0 1 7.426-3.071 6.187 6.187 0 0 1-2.432 12.05.563.563 0 0 0-.103 1.12A7.312 7.312 0 1 0 9 1.688Z"
            />
            <path
              fill="#B3B3B3"
              d="M9 4.5a.562.562 0 0 0-.563.563v4.5a.563.563 0 0 0 .563.562h4.5A.562.562 0 1 0 13.5 9H9.562V5.062A.563.563 0 0 0 9 4.5ZM6.75 9.563h-4.5a.562.562 0 1 0 0 1.124h4.5a.562.562 0 1 0 0-1.124ZM6.75 15.188h-4.5a.562.562 0 1 0 0 1.124h4.5a.562.562 0 1 0 0-1.125ZM6.75 12.375h-4.5a.562.562 0 1 0 0 1.125h4.5a.562.562 0 1 0 0-1.125Z"
            />
          </svg>
          </Tooltip>
        </div>
      </button>
      <div
        style={{
          display: isLeftSidebarOpen ? "block" : "none",
        }}
      />
      <LoadModel open={open} setOpen={setOpen} />
      <div className="flex items-center gap-[.5rem]">
        <button
          style={{
            display: isRightSidebarOpen ? "none" : "block",
          }}
          className="w-[1.475rem] height-[1.475rem] p-[.2rem] rounded-[6px] flex justify-center items-center cursor-pointer"
          onClick={onToggleRightSidebar}
        >
          <div className="w-[1.125rem] h-[1.125rem] flex justify-center items-center cursor-pointer group text-[#B3B3B3] hover:text-[#FFFFFF]">
          <Tooltip title="Settings">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="18"
              height="18"
              fill="none"
            >
              <path
                fill="currentColor"
                d="M16.313 3.563H14.55a2.39 2.39 0 0 0-2.317-1.828 2.39 2.39 0 0 0-2.316 1.828h-8.23a.562.562 0 1 0 0 1.125h8.23a2.39 2.39 0 0 0 2.316 1.828 2.39 2.39 0 0 0 2.317-1.828h1.761a.562.562 0 1 0 0-1.125ZM12.235 5.39a1.267 1.267 0 0 1 0-2.531 1.267 1.267 0 0 1 0 2.53ZM16.313 8.437h-8.23A2.39 2.39 0 0 0 5.765 6.61a2.39 2.39 0 0 0-2.317 1.828H1.688a.562.562 0 1 0 0 1.125h1.76a2.39 2.39 0 0 0 2.318 1.829 2.39 2.39 0 0 0 2.316-1.829h8.23a.562.562 0 1 0 0-1.125ZM5.765 10.266a1.267 1.267 0 0 1 0-2.532 1.267 1.267 0 0 1 0 2.531ZM16.313 13.312H14.55a2.39 2.39 0 0 0-2.317-1.828 2.39 2.39 0 0 0-2.316 1.828h-8.23a.562.562 0 1 0 0 1.125h8.23a2.39 2.39 0 0 0 2.316 1.828 2.39 2.39 0 0 0 2.317-1.828h1.761a.562.562 0 1 0 0-1.125Zm-4.078 1.828a1.267 1.267 0 0 1 0-2.53 1.267 1.267 0 0 1 0 2.53Z"
              />
            </svg>
            </Tooltip>
          </div>
        </button>
        <button
          onClick={() => {
            createChat();
          }}
          className="w-[1.475rem] height-[1.475rem] p-[.2rem] rounded-[6px] flex justify-center items-center cursor-pointer"
        >
          <div className="w-[1.125rem] h-[1.125rem] flex justify-center items-center cursor-pointer group text-[#B3B3B3] hover:text-[#FFFFFF]">
          <Tooltip title="New chat window">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="18"
              height="18"
              fill="none"
            >
              <path
                fill="currentColor"
                d="M9 2a.757.757 0 0 0-.757.757v5.486H2.757a.757.757 0 0 0 0 1.514h5.486v5.486a.757.757 0 0 0 1.514 0V9.757h5.486a.757.757 0 0 0 0-1.514H9.757V2.757A.757.757 0 0 0 9 2Z"
              />
            </svg>
          </Tooltip>
          </div>
        </button>
        <DropdownMenu
          open={openDropdown}
          onOpenChange={(isOpen) => setOpenDropdown(isOpen)}
        >
          <DropdownMenuTrigger>
            <div className="mr-[.4rem] w-[1.475rem] height-[1.475rem] p-[.2rem] rounded-[6px] flex justify-center items-center  cursor-pointer">
              <div className="w-[1.125rem] h-[1.125rem] flex justify-center items-center cursor-pointer group text-[#B3B3B3] hover:text-[#FFFFFF]">
              <Tooltip title="Options">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="18"
                  height="18"
                  fill="none"
                >
                  <path
                    fill="currentColor"
                    fillRule="evenodd"
                    d="M10.453 3.226a1.226 1.226 0 1 1-2.453 0 1.226 1.226 0 0 1 2.453 0Zm0 5.45a1.226 1.226 0 1 1-2.453 0 1.226 1.226 0 0 1 2.453 0Zm-1.226 6.676a1.226 1.226 0 1 0 0-2.452 1.226 1.226 0 0 0 0 2.452Z"
                    clipRule="evenodd"
                  />
                </svg>
                </Tooltip>
              </div>
            </div>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="bg-[#101010] border-[1px] border-[#1F1F1F]">
            {chat && (
              <DropdownMenuItem
                className="cursor-pointer text-[#B3B3B3] hover:text-white"
                onClick={() => {
                  setOpenDropdown(false);
                  setMessages([]);
                  closeChat(chat);
                  setChatData([]);
                }}
              >
                Close
              </DropdownMenuItem>
            )}
            <DropdownMenuItem
              onClick={async () => {
                if (chat) {
                  localStorage.removeItem(chat?.id);
                  setChatData([]);
                  setMessages([]);
                }
              }}
              className="cursor-pointer text-[#B3B3B3] hover:text-white"
            >
              Clear History
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={async () => {
                if (chat) {
                  await deleteSession(chat?.id);
                  setMessages([]);
                  setChatData([]);
                  closeChat(chat);
                }
              }}
              className="cursor-pointer text-[#B3B3B3] hover:text-white"
            >
              Delete
            </DropdownMenuItem>
            {/* <DropdownMenuItem>Profile</DropdownMenuItem>
           
            <DropdownMenuItem>Subscription</DropdownMenuItem> */}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}

export default NavBar;
