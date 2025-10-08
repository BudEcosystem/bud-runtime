'use client';

import React from 'react';
import { CloseOutlined } from "@ant-design/icons";
import { Image, Select } from "antd";
import { PrimaryButton } from "../../ui/bud/form/Buttons";
import { Text_14_400_757575, Text_16_400_EEEEEE } from "../../ui/text";
import { TextAreaInput } from "../../ui/input";

interface PromptMessage {
  id: string;
  role: 'system' | 'user' | 'assistant';
  content: string;
}

interface PromptMessageSettingsProps {
  sessionId: string;
  promptMessages: string;
  onPromptMessagesChange: (value: string) => void;
}

export const PromptMessageSettings: React.FC<PromptMessageSettingsProps> = ({
  sessionId: _sessionId,
  promptMessages,
  onPromptMessagesChange
}) => {
  // Parse the string to array if needed, or start with default
  const [messages, setMessages] = React.useState<PromptMessage[]>(() => {
    try {
      if (promptMessages && typeof promptMessages === 'string' && promptMessages.startsWith('[')) {
        return JSON.parse(promptMessages);
      }
    } catch (e) {
      // Invalid JSON, use default
    }
    return [{
      id: `msg_${Date.now()}`,
      role: 'system',
      content: ''
    }];
  });

  const [messageOpenStates, setMessageOpenStates] = React.useState<Record<string, boolean>>({});

  // Initialize first message as open
  React.useEffect(() => {
    if (messages.length > 0 && Object.keys(messageOpenStates).length === 0) {
      setMessageOpenStates({ [messages[0].id]: true });
    }
  }, [messages, messageOpenStates]);

  const handleAddMessage = () => {
    const newMessage: PromptMessage = {
      id: `msg_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`,
      role: 'user',
      content: ''
    };
    const updatedMessages = [...messages, newMessage];
    setMessages(updatedMessages);
    setMessageOpenStates(prev => ({ ...prev, [newMessage.id]: true }));
    // Store as JSON string for compatibility
    onPromptMessagesChange(JSON.stringify(updatedMessages));
  };

  const handleMessageChange = (messageId: string, field: keyof PromptMessage, value: any) => {
    const updatedMessages = messages.map(msg =>
      msg.id === messageId ? { ...msg, [field]: value } : msg
    );
    setMessages(updatedMessages);
    onPromptMessagesChange(JSON.stringify(updatedMessages));
  };

  const handleDeleteMessage = (messageId: string) => {
    if (messages.length <= 1) return; // Keep at least one message
    const updatedMessages = messages.filter(msg => msg.id !== messageId);
    setMessages(updatedMessages);
    const newOpenStates = { ...messageOpenStates };
    delete newOpenStates[messageId];
    setMessageOpenStates(newOpenStates);
    onPromptMessagesChange(JSON.stringify(updatedMessages));
  };

  const toggleMessageOpen = (messageId: string) => {
    setMessageOpenStates(prev => ({
      ...prev,
      [messageId]: !prev[messageId]
    }));
  };

  const getRoleDisplayName = (role: string) => {
    return role.charAt(0).toUpperCase() + role.slice(1);
  };

  return (
    <div className="flex flex-col w-full px-[.4rem] py-[1rem]">
      <div className='flex flex-col gap-[1rem] border-b border-[#1F1F1F] pb-[1rem]'>
        <div className="flex flex-row items-center gap-[.2rem] px-[.3rem] justify-between">
          <div className="flex flex-row items-center py-[.5rem]">
            <Text_16_400_EEEEEE className='text-nowrap'>Prompt Messages</Text_16_400_EEEEEE>
          </div>
          <div className="flex flex-row items-center gap-[.5rem]">
            <PrimaryButton
              size="small"
              onClick={(e: React.MouseEvent) => {
                e.stopPropagation();
                handleAddMessage();
              }}
              classNames="h-[1.375rem] rounded-[6px] py-[0] pl-[.3rem] pr-[.3rem]"
              textClassName="!text-[0.625rem]"
            >
              + Add Role
            </PrimaryButton>
          </div>
        </div>
      </div>

      {/* Messages Section */}
      <div className="">
        {messages.map((message) => (
          <div key={message.id} className="border-b border-[#1F1F1F]">
            <div className='py-[1rem]'>
              <div
                className='flex justify-between items-center px-[.5rem] cursor-pointer'
                onClick={() => toggleMessageOpen(message.id)}
              >
                <Text_14_400_757575>
                  {messageOpenStates[message.id] ? getRoleDisplayName(message.role) : getRoleDisplayName(message.role)}
                </Text_14_400_757575>
                <div className="flex items-center gap-2">
                  <Image
                    src="/icons/customArrow.png"
                    className={`w-[.75rem] transform transition-transform rotate-0 ${messageOpenStates[message.id] ? "" : "rotate-180"}`}
                    preview={false}
                    alt="chevron"
                  />
                </div>
              </div>

              {messageOpenStates[message.id] && (
                <div className="px-[.5rem] pt-4">
                  <div className="relative group rounded-lg transition-colors">
                    {/* Delete button */}
                    {messages.length > 1 && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteMessage(message.id);
                        }}
                        className="absolute top-0 right-0 p-1 opacity-100 transition-opacity z-10"
                      >
                        <CloseOutlined className="text-[#808080] hover:text-[#FF4444] text-xs" />
                      </button>
                    )}

                    <div className="space-y-3">
                      {/* Role Select */}
                      <div className="flex flex-col gap-1">
                        <Select
                          className="!w-full custom-select"
                          value={message.role}
                          onChange={(value) => handleMessageChange(message.id, 'role', value)}
                          placeholder="Select role"
                          options={[
                            { value: 'system', label: 'System' },
                            { value: 'user', label: 'User' },
                            { value: 'assistant', label: 'Assistant' }
                          ]}
                          style={{
                            height: '32px',
                            fontSize: '12px'
                          }}
                        />
                      </div>

                      {/* Message Content */}
                      <div className="flex flex-col gap-1">
                        <TextAreaInput
                          className="!w-full !max-w-full !min-h-[3rem] !text-[#EEEEEE] !text-xs placeholder:!text-[#606060] !border-[#2A2A2A] hover:!border-[#965CDE] focus:!border-[#965CDE] px-[.4rem]  placeholder:text-[#757575] placeholder:opacity-100 placeholder:text-[.75rem]"
                          value={message.content}
                          onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
                            handleMessageChange(message.id, 'content', e.target.value)
                          }
                          placeholder="Enter Message"
                          style={{ color: '#EEEEEE' }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
