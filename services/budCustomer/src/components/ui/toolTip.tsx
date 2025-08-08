import React, { useState } from "react";

interface ToolTipProps {
  triggerRenderItem: React.ReactNode;
  contentRenderItem: React.ReactNode;
  renderItemClassName?: string;
  arrowClasses?: string;
  align?: "start" | "center" | "end";
  side?: "top" | "right" | "bottom" | "left";
}

const ToolTip: React.FC<ToolTipProps> = ({
  triggerRenderItem,
  contentRenderItem,
  renderItemClassName,
  arrowClasses,
  align = "start",
  side = "top",
}) => {
  const [isVisible, setIsVisible] = useState(false);

  const getTooltipPosition = () => {
    const baseClasses = "absolute z-50 select-none rounded-[6px] px-[15px] py-[10px] text-[15px] leading-none shadow-lg bg-gray-900 text-white opacity-0 transition-opacity duration-200";

    let positionClasses = "";

    switch (side) {
      case "top":
        positionClasses = "bottom-full left-1/2 transform -translate-x-1/2 mb-2";
        if (align === "start") positionClasses = "bottom-full left-0 mb-2";
        if (align === "end") positionClasses = "bottom-full right-0 mb-2";
        break;
      case "bottom":
        positionClasses = "top-full left-1/2 transform -translate-x-1/2 mt-2";
        if (align === "start") positionClasses = "top-full left-0 mt-2";
        if (align === "end") positionClasses = "top-full right-0 mt-2";
        break;
      case "left":
        positionClasses = "right-full top-1/2 transform -translate-y-1/2 mr-2";
        if (align === "start") positionClasses = "right-full top-0 mr-2";
        if (align === "end") positionClasses = "right-full bottom-0 mr-2";
        break;
      case "right":
        positionClasses = "left-full top-1/2 transform -translate-y-1/2 ml-2";
        if (align === "start") positionClasses = "left-full top-0 ml-2";
        if (align === "end") positionClasses = "left-full bottom-0 ml-2";
        break;
    }

    return `${baseClasses} ${positionClasses} ${isVisible ? 'opacity-100' : 'opacity-0 pointer-events-none'} ${renderItemClassName}`;
  };

  return (
    <div className="relative inline-block">
      <div
        className="cursor-pointer"
        onMouseEnter={() => setIsVisible(true)}
        onMouseLeave={() => setIsVisible(false)}
      >
        {triggerRenderItem}
      </div>
      <div className={getTooltipPosition()}>
        {contentRenderItem}
        {/* Arrow - simplified without complex positioning */}
        <div className={`absolute w-2 h-2 bg-gray-900 transform rotate-45 ${arrowClasses}`} />
      </div>
    </div>
  );
};

export default ToolTip;
