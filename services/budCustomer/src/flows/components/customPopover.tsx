import React from 'react';
import { Popover } from 'antd';

interface CustomPopoverProps {
  title?: string;
  children: React.ReactNode;
  contentClassNames?: string;
  customClassName?: string;
}

export default function CustomPopover({
  title,
  children,
  contentClassNames,
  customClassName
}: CustomPopoverProps) {
  return (
    <Popover
      content={<div className={contentClassNames}>{title}</div>}
      className={customClassName}
    >
      {children}
    </Popover>
  );
}
