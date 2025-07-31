import React from 'react';
import { Tag } from 'antd';

export interface TagListeItem {
  name: string;
  color: string;
  icon?: React.ReactNode;
}

interface TagsListProps {
  data?: TagListeItem[];
}

export default function TagsList({ data = [] }: TagsListProps) {
  return (
    <>
      {data.map((item, index) => (
        <Tag 
          key={index} 
          color={item.color}
          className="border-0 px-[0.75rem] py-[0.25rem] text-[0.75rem]"
        >
          {item.icon && item.icon}
          {item.name}
        </Tag>
      ))}
    </>
  );
}