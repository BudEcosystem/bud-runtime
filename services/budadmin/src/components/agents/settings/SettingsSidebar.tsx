import React from "react";
import Settings from "./Settings";

interface SettingsSidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export function SettingsSidebar({ isOpen, onClose }: SettingsSidebarProps) {
  if (!isOpen) return null;

  return (
    <div
      className="z-[100] tools-box absolute p-3 right-0 top-0 h-full transition-all duration-300 ease-in-out translate-x-0"
      onClick={(e) => e.stopPropagation()}
    >
      <div
        className="flex flex-col h-full w-[16rem] prompt-settings overflow-y-auto rounded-[12px]"
        style={{
          backgroundImage: 'url(/agents/settingsBg.png)',
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat'
        }}
      >
        <Settings />
      </div>
      {/* <div className="flex flex-col h-full">
]        <div className="flex items-center justify-between p-4 border-b border-[#1F1F1F]">
          <h3 className="text-[#EEEEEE] text-sm font-medium">Model Settings</h3>
          <button
            onClick={onClose}
            className="text-[#B3B3B3] hover:text-[#FFFFFF] transition-colors"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="18"
              height="18"
              viewBox="0 0 18 18"
              fill="none"
            >
              <path
                d="M13.5 4.5L4.5 13.5M4.5 4.5L13.5 13.5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          <Settings />
        </div>
      </div> */}
    </div>
  );
}
