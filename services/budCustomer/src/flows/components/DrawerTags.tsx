import React from 'react';
import { Tag } from 'antd';

interface TagsProps {
  tags?: string[];
  color?: string;
  className?: string;
}

const Tags: React.FC<TagsProps> = ({
  tags = [],
  color = 'blue',
  className = ''
}) => {
  if (!tags || tags.length === 0) {
    return null;
  }

  return (
    <div className={`flex gap-1 flex-wrap ${className}`}>
      {tags.map((tag, index) => (
        <Tag key={index} color={color} className="text-xs">
          {tag}
        </Tag>
      ))}
    </div>
  );
};

export default Tags;
