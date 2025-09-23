'use client';

import React, { useState } from "react";
import { Button, Dropdown, Tooltip, Image } from "antd";
import {
  PlusOutlined,
  CloseOutlined,
  CopyOutlined,
  DeleteOutlined,
} from "@ant-design/icons";
import { useAgentStore, AgentSession, AgentVariable } from "@/stores/useAgentStore";
import LoadModel from "./LoadModel";
import { PrimaryButton } from "../ui/bud/form/Buttons";
import { Text_14_400_757575 } from "../ui/text";
import { TextInput, TextAreaInput } from "../ui/input";
import { Editor } from "../flowgramEditorDemo/editor";

interface AgentBoxProps {
  session: AgentSession;
  index: number;
  totalSessions: number;
  onToggleRightSidebar?: () => void;
  isRightSidebarOpen?: boolean;
}

function AgentBox({
  session,
  index,
  totalSessions,
  onToggleRightSidebar,
  isRightSidebarOpen = false
}: AgentBoxProps) {
  // All hooks must be called before any conditional returns
  const {
    updateSession,
    deleteSession,
    duplicateSession,
    addInputVariable,
    addOutputVariable,
    updateVariable,
    deleteVariable,
    createSession,
  } = useAgentStore();

  const [localSystemPrompt, setLocalSystemPrompt] = useState(session?.systemPrompt || "");
  const [localPromptMessages, setLocalPromptMessages] = useState(session?.promptMessages || "");
  const [openLoadModel, setOpenLoadModel] = useState(false);
  const [openInput, setOpenInput] = useState(true);
  const [openSystemPrompt, setOpenSystemPrompt] = useState(true);
  const [openPromptMessages, setOpenPromptMessages] = useState(true);
  const [openOutput, setOpenOutput] = useState(true);

  // Handle case where session is null early
  if (!session) {
    return (
      <div className="agent-box flex flex-col bg-[#0A0A0A] border border-[#1F1F1F] rounded-lg min-w-[400px] h-full overflow-hidden justify-center items-center">
        <span className="text-[#808080]">No session data available</span>
      </div>
    );
  }

  const handleAddVariable = () => {
    if (session) addInputVariable(session.id);
  };

  const handleVariableChange = (variableId: string, field: keyof AgentVariable, value: string) => {
    if (session) updateVariable(session.id, variableId, { [field]: value });
  };

  const handleDeleteVariable = (variableId: string) => {
    if (session) deleteVariable(session.id, variableId);
  };

  const menuItems = [
    {
      key: 'duplicate',
      icon: <CopyOutlined />,
      label: 'Duplicate',
      onClick: () => session && duplicateSession(session.id)
    },
    {
      key: 'delete',
      icon: <DeleteOutlined />,
      label: 'Delete',
      danger: true,
      onClick: () => session && deleteSession(session.id)
    }
  ];

  // All boxes are expanded by default
  const boxWidth = "600px";

  return (
    <div
      className="agent-box flex flex-col bg-[#0A0A0A] border border-[#1F1F1F] rounded-lg min-w-[400px] h-full overflow-hidden"
      style={{ width: boxWidth, transition: "width 0.3s ease" }}
    >
      {/* Navigation Bar */}
      <div className="topBg text-white p-4 flex justify-between items-center h-[3.625rem] relative sticky top-0 z-10 bg-[#101010] border-b border-[#1F1F1F]">
        {/* Left Section - Session Info and Load Model */}
        <div className="flex items-center gap-3">
          <span className="text-[#808080] text-xs font-medium">V{index + 1}</span>
        </div>

        {/* Center Section - Load Model */}
        <LoadModel
          sessionId={session?.id || ''}
          open={openLoadModel}
          setOpen={setOpenLoadModel}
        />

        {/* Right Section - Action Buttons */}
        <div className="flex items-center gap-1">
          {/* Settings Button */}
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

          {/* New Chat Window Button */}
          <Tooltip title="New chat window" placement="bottom">
            <button
              onClick={createSession}
              className="w-7 h-7 rounded-md flex justify-center items-center cursor-pointer hover:bg-[#1A1A1A] transition-colors"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="18"
                height="18"
                fill="none"
                className="text-[#B3B3B3] hover:text-white"
              >
                <path
                  fill="currentColor"
                  d="M9 2a.757.757 0 0 0-.757.757v5.486H2.757a.757.757 0 0 0 0 1.514h5.486v5.486a.757.757 0 0 0 1.514 0V9.757h5.486a.757.757 0 0 0 0-1.514H9.757V2.757A.757.757 0 0 0 9 2Z"
                />
              </svg>
            </button>
          </Tooltip>

          {/* More Options Dropdown */}
          <Dropdown menu={{ items: menuItems }} trigger={["click"]} placement="bottomRight">
            <Tooltip title="Options" placement="bottom">
              <button className="w-7 h-7 rounded-md flex justify-center items-center cursor-pointer hover:bg-[#1A1A1A] transition-colors">
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
                    className="text-[#B3B3B3] hover:text-white"
                  />
                </svg>
              </button>
            </Tooltip>
          </Dropdown>

          {/* Close Button */}
          {totalSessions > 1 && (
            <Tooltip title="Close" placement="bottom">
              <button
                onClick={() => session && deleteSession(session.id)}
                className="w-7 h-7 rounded-md flex justify-center items-center cursor-pointer hover:bg-[#1A1A1A] transition-colors"
              >
                <CloseOutlined className="text-[#B3B3B3] hover:text-[#FF4444] text-base" />
              </button>
            </Tooltip>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden relative">
        <div className={`flex w-full h-full transition-all duration-300 ease-in-out ${isRightSidebarOpen ? 'pr-[15rem]' : 'pr-0'}`}>
          {/* Main content area */}
          <div className="flex-1 p-4 flow-editor-container">

            <Editor />

          </div>

          {/* Settings Sidebar */}
          <div className={`settings-box absolute p-3 right-0 top-0 h-full  transition-all duration-300 ease-in-out ${isRightSidebarOpen ? 'translate-x-0' : 'translate-x-full'
            }`}>
            <div className="flex flex-col h-full w-[15rem] py-3 prompt-settings border border-[#1F1F1F] bg-[#0A0A0A] overflow-y-auto rounded-[12px]">
              {/* Input Section */}
              <div className="flex flex-col w-full px-[.4rem] py-[1.5rem] border-b border-[#1F1F1F]">
                <div
                  className="flex flex-row items-center gap-[1rem] px-[.3rem] justify-between cursor-pointer"
                  onClick={() => setOpenInput(!openInput)}
                >
                  <div className="flex flex-row items-center gap-[.4rem] py-[.5rem]">
                    <Text_14_400_757575>Input</Text_14_400_757575>
                  </div>
                  <div className="flex flex-row items-center gap-[.5rem]">
                    <PrimaryButton
                      size="small"
                      onClick={(e: React.MouseEvent) => {
                        e.stopPropagation();
                        handleAddVariable();
                      }}
                      className="bg-[#965CDE] border-none text-white hover:bg-[#8050C8] h-6 px-2 text-xs !rounded-[12px]"
                    >
                      + Add Variable
                    </PrimaryButton>
                    <Image
                      src="/icons/customArrow.png"
                      className={`w-[.75rem] transform transition-transform rotate-0 ${openInput ? "" : "rotate-180"}`}
                      preview={false}
                      alt="chevron"
                    />
                  </div>
                </div>
                {openInput && (
                  <div className="space-y-2 px-[.5rem] pt-2">
                    {(session?.inputVariables || []).map((variable, idx) => (
                      <div key={variable.id} className="relative group">
                        <div className="relative">
                          <TextInput
                            className="!w-full !max-w-full !h-[2rem] !text-[#EEEEEE] !text-xs !placeholder-[#606060] !border-[#2A2A2A] hover:!border-[#965CDE] focus:!border-[#965CDE] px-[.4rem]"
                            value={variable.value}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleVariableChange(variable.id, "value", e.target.value)}
                            placeholder={`Input Variable ${idx + 1}`}
                          />
                          {(session?.inputVariables?.length || 0) > 1 && (
                            <button
                              onClick={() => handleDeleteVariable(variable.id)}
                              className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                              <CloseOutlined className="text-[#808080] hover:text-[#FF4444] text-xs" />
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* System Prompt Section */}
              <div className="flex flex-col w-full px-[.4rem] py-[1rem] border-b border-[#1F1F1F]">
                <div
                  className="flex flex-row items-center gap-[1rem] px-[.3rem] justify-between cursor-pointer"
                  onClick={() => setOpenSystemPrompt(!openSystemPrompt)}
                >
                  <div className="flex flex-row items-center gap-[.4rem] py-[.5rem]">
                    <Text_14_400_757575>System Prompt</Text_14_400_757575>
                  </div>
                  <div className="flex flex-row items-center">
                    <Image
                      src="/icons/customArrow.png"
                      className={`w-[.75rem] transform transition-transform rotate-0 ${openSystemPrompt ? "" : "rotate-180"}`}
                      preview={false}
                      alt="chevron"
                    />
                  </div>
                </div>
                {openSystemPrompt && (
                  <div className="space-y-2 px-[.5rem] pt-2">
                    <TextAreaInput
                      className="!w-full !max-w-full !min-h-[4rem] !text-[#EEEEEE] !text-xs !placeholder-[#606060] !border-[#2A2A2A] hover:!border-[#965CDE] focus:!border-[#965CDE]"
                      value={localSystemPrompt}
                      onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => {
                        setLocalSystemPrompt(e.target.value);
                        if (session) updateSession(session.id, { systemPrompt: e.target.value });
                      }}
                      placeholder="Enter System Prompt..."
                    />
                  </div>
                )}
              </div>

              {/* Prompt Messages Section */}
              <div className="flex flex-col w-full px-[.4rem] py-[1rem] border-b border-[#1F1F1F]">
                <div
                  className="flex flex-row items-center gap-[1rem] px-[.3rem] justify-between cursor-pointer"
                  onClick={() => setOpenPromptMessages(!openPromptMessages)}
                >
                  <div className="flex flex-row items-center gap-[.4rem] py-[.5rem]">
                    <Text_14_400_757575>Prompt Messages</Text_14_400_757575>
                  </div>
                  <div className="flex flex-row items-center">
                    <Image
                      src="/icons/customArrow.png"
                      className={`w-[.75rem] transform transition-transform rotate-0 ${openPromptMessages ? "" : "rotate-180"}`}
                      preview={false}
                      alt="chevron"
                    />
                  </div>
                </div>
                {openPromptMessages && (
                  <div className="space-y-2 px-[.5rem] pt-2">
                    <div className="border border-[#2A2A2A] rounded-md p-2 min-h-[100px]">
                      <TextAreaInput
                        className="!w-full !max-w-full !border-0 !p-0 !min-h-[4rem] !text-[#EEEEEE] !text-xs !placeholder-[#606060]"
                        value={localPromptMessages}
                        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => {
                          setLocalPromptMessages(e.target.value);
                          if (session) updateSession(session.id, { promptMessages: e.target.value });
                        }}
                        placeholder="Add Prompt Messages..."
                      />
                      <div className="flex justify-between items-center mt-2 pt-2 border-t border-[#1A1A1A]">
                        <span className="text-[#606060] text-xs">53%</span>
                        <button className="text-[#606060] hover:text-[#965CDE] text-xs">
                          <PlusOutlined className="mr-1" />
                          Add
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Output Variables Section */}
              <div className="flex flex-col w-full px-[.4rem] py-[1rem]">
                <div
                  className="flex flex-row items-center gap-[1rem] px-[.3rem] justify-between cursor-pointer"
                  onClick={() => setOpenOutput(!openOutput)}
                >
                  <div className="flex flex-row items-center gap-[.4rem] py-[.5rem]">
                    <Text_14_400_757575>Output</Text_14_400_757575>
                  </div>
                  <div className="flex flex-row items-center gap-[.5rem]">
                    <Button
                      size="small"
                      icon={<PlusOutlined />}
                      onClick={(e: React.MouseEvent) => {
                        e.stopPropagation();
                        addOutputVariable(session.id);
                      }}
                      className="bg-[#5CADFF] border-none text-white hover:bg-[#4A9AED] h-6 px-2 text-xs"
                    >
                      Add Variable
                    </Button>
                    <Image
                      src="/icons/customArrow.png"
                      className={`w-[.75rem] transform transition-transform rotate-0 ${openOutput ? "" : "rotate-180"}`}
                      preview={false}
                      alt="chevron"
                    />
                  </div>
                </div>
                {openOutput && (
                  <div className="space-y-2 px-[.5rem] pt-2">
                    {(session?.outputVariables || []).map((variable, idx) => (
                      <div key={variable.id} className="relative group">
                        <div className="relative">
                          <TextInput
                            className="!w-full !max-w-full !h-[2rem] !text-[#EEEEEE] !text-xs !placeholder-[#606060] !border-[#2A2A2A] hover:!border-[#5CADFF] focus:!border-[#5CADFF] px-[.4rem]"
                            value={variable.value}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleVariableChange(variable.id, "value", e.target.value)}
                            placeholder={`Output Variable ${idx + 1}`}
                            readOnly
                          />
                          <button
                            onClick={() => handleDeleteVariable(variable.id)}
                            className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            <CloseOutlined className="text-[#808080] hover:text-[#FF4444] text-xs" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AgentBox;
