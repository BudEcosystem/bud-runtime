'use client';

import React from 'react';
import { CloseOutlined } from "@ant-design/icons";
import { Image, Select } from "antd";
import { PrimaryButton } from "../../ui/bud/form/Buttons";
import { Text_14_400_757575, Text_16_400_EEEEEE } from "../../ui/text";
import { TextAreaInput } from "../../ui/input";

interface PromptMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

interface PromptMessageSettingsProps {
  sessionId: string;
  promptMessages: string;
  onPromptMessagesChange: (value: string) => void;
  onSavePromptMessages?: () => void;
  isSavingPromptMessages?: boolean;
}

export const PromptMessageSettings: React.FC<PromptMessageSettingsProps> = ({
  sessionId: _sessionId,
  promptMessages,
  onPromptMessagesChange,
  onSavePromptMessages,
  isSavingPromptMessages
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
      role: 'user',
      content: ''
    }];
  });

  const [messageOpenStates, setMessageOpenStates] = React.useState<Record<string, boolean>>({});

  // Sync messages state when promptMessages prop changes (e.g., from external delete or clear)
  React.useEffect(() => {
    try {
      // Handle empty/cleared prompt messages - reset to default empty state
      if (!promptMessages || promptMessages === '[]' || promptMessages === '') {
        const defaultMessage: PromptMessage = {
          id: `msg_${Date.now()}`,
          role: 'user',
          content: ''
        };
        setMessages([defaultMessage]);
        setMessageOpenStates({ [defaultMessage.id]: true });
        return;
      }

      if (typeof promptMessages === 'string' && promptMessages.startsWith('[')) {
        const parsedMessages = JSON.parse(promptMessages);
        // If parsed array is empty, reset to default
        if (parsedMessages.length === 0) {
          const defaultMessage: PromptMessage = {
            id: `msg_${Date.now()}`,
            role: 'user',
            content: ''
          };
          setMessages([defaultMessage]);
          setMessageOpenStates({ [defaultMessage.id]: true });
        } else {
          setMessages(parsedMessages);
        }
      }
    } catch (e) {
      // Invalid JSON, keep current state
      console.error('Error parsing promptMessages:', e);
    }
  }, [promptMessages]);

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

  return (
    <div className="flex flex-col justify-between h-full w-full">
      <div className='flex flex-col px-[.4rem] py-[1rem]'>
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
                classNames="h-[1.375rem] rounded-[0.375rem]"
                textClass="!text-[0.625rem] !font-[400]"
              >
                + Add Role
              </PrimaryButton>
            </div>
          </div>
        </div>

        {/* Messages Section */}
        <div className="pt-[1.5rem]">
          {messages.map((message) => (
            <div key={message.id} className="bg-[#FFFFFF08] px-[.725rem] py-[.725rem] rounded-[.5rem] border border-[#1F1F1F] mb-[.75rem]">
              <div className=''>
                <div
                  className='group flex justify-between items-center cursor-pointer'
                  onClick={() => toggleMessageOpen(message.id)}
                >
                  {/* Role Select */}
                  <div className="flex flex-col gap-1">
                    <style jsx global>{`
                                .input-user-select.ant-select .ant-select-selector {
                                  padding-left: .625rem !important;
                                  padding-right: .625rem !important;
                                  background-color: #FFFFFF08 !important;
                                  height: 1.25rem !important;
                                  border: none !important;
                                }
                                .input-user-select.ant-select .ant-select-arrow {
                                  margin-top: -8px !important;
                                }
                              `}</style>
                    <Select
                      className="!w-full custom-select input-user-select"
                      value={message.role}
                      onChange={(value) => handleMessageChange(message.id, 'role', value)}
                      placeholder="Select role"
                      options={[
                        { value: 'user', label: 'User' },
                        { value: 'assistant', label: 'Assistant' }
                      ]}
                      style={{
                        // height: '1.25rem',
                        fontSize: '.75rem',
                      }}
                    />
                  </div>
                  <div className='flex justify-end items-center'>
                    {/* Delete button */}
                    {messages.length > 1 && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteMessage(message.id);
                        }}
                        className="opacity-0 transition-opacity z-10 p-0 mr-[.6rem] group-hover:opacity-100"
                      >
                        <CloseOutlined className="text-[#808080] hover:text-[#FF4444] text-[.7rem]" />
                      </button>
                    )}
                    <div className="flex items-center gap-2">
                      <Image
                        src="/icons/customArrow.png"
                        className={`w-[.75rem] transform transition-transform rotate-0 ${messageOpenStates[message.id] ? "" : "rotate-180"}`}
                        preview={false}
                        alt="chevron"
                      />
                    </div>
                  </div>

                </div>

                {messageOpenStates[message.id] && (
                  <div className=" pt-4">
                    <div className="relative group rounded-lg transition-colors">


                      <div className="space-y-3">


                        {/* Message Content */}
                        <div className="flex flex-col gap-1">
                          <TextAreaInput
                            className="!w-full !max-w-full !min-h-[3rem] !text-[#EEEEEE] !text-xs placeholder:!text-[#606060] !border-[#2A2A2A] hover:!border-[#965CDE] focus:!border-[#965CDE] px-[.4rem]  placeholder:text-[#757575] placeholder:opacity-100 placeholder:text-[.75rem] resize-y"
                            value={message.content}
                            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
                              handleMessageChange(message.id, 'content', e.target.value)
                            }
                            placeholder="Enter Message"
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

      <div style={{
        marginTop: '18px',
        paddingTop: '18px',
        paddingBottom: '18px',
        borderRadius: '0 0 11px 11px',
        borderTop: '0.5px solid #1F1F1F',
        background: 'rgba(255, 255, 255, 0.03)',
        backdropFilter: 'blur(5px)'
      }} className='flex justify-end items-center px-[1rem]'>
        <PrimaryButton
          onClick={(e: React.MouseEvent) => {
            e.stopPropagation();
            onSavePromptMessages?.();
          }}
          loading={isSavingPromptMessages}
          disabled={isSavingPromptMessages}
          style={{
            cursor: isSavingPromptMessages ? 'not-allowed' : 'pointer',
          }}
          classNames="h-[1.375rem] rounded-[0.375rem]"
          textClass="!text-[0.625rem] !font-[400]"

        >
          {isSavingPromptMessages ? 'Updating...' : 'Update'}
        </PrimaryButton>
      </div>
    </div>
  );
};
