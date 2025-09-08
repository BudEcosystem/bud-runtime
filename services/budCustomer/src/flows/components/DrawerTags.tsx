import React from "react";
import { Tag, Tooltip } from "antd";

interface TagsProps {
  tags?: string[];
  name?: string | number;
  color?: string;
  className?: string;
  textClass?: string;
  image?: React.ReactElement;
  onTagClick?: () => void;
  tooltipText?: string;
  copyText?: string;
  showTooltip?: boolean;
}

const Tags: React.FC<TagsProps> = ({
  tags = [],
  name,
  color = "blue",
  className = "",
  textClass = "",
  image,
  onTagClick,
  tooltipText,
  copyText,
  showTooltip,
}) => {
  // If tags array is provided, render multiple tags
  if (tags && tags.length > 0) {
    return (
      <div className={`flex gap-1 flex-wrap ${className}`}>
        {tags.map((tag, index) => (
          <Tag key={index} color={color} className="text-xs">
            {tag}
          </Tag>
        ))}
      </div>
    );
  }

  // If name is provided, render single tag
  if (name !== undefined && name !== null) {
    const tagContent = (
      <div
        className={`flex items-center px-2 py-1 rounded text-white ${textClass} ${onTagClick ? "cursor-pointer" : ""}`}
        style={{ backgroundColor: color }}
        onClick={onTagClick}
      >
        {image}
        <span>{name}</span>
      </div>
    );

    if (showTooltip && tooltipText) {
      return <Tooltip title={tooltipText}>{tagContent}</Tooltip>;
    }

    return tagContent;
  }

  return null;
};

export default Tags;
