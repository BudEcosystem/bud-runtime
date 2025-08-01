import { Dropdown, Menu } from 'antd';
import { ReactNode } from 'react';

interface CustomDropDownProps {
  items: { key: string; label: string; value?: any; onClick?: () => void }[];
  Placement?: 'bottomLeft' | 'bottomCenter' | 'bottomRight' | 'topLeft' | 'topCenter' | 'topRight';
  menuItemColor?: string;
  parentClassNames?: string;
  buttonContent: ReactNode;
  onSelect?: (item: any) => void;
}

export default function CustomDropDown({
  items,
  Placement = 'bottomLeft',
  menuItemColor = '#EEEEEE',
  parentClassNames = '',
  buttonContent,
  onSelect
}: CustomDropDownProps) {
  const menuItems = items.map(item => ({
    key: item.key,
    label: (
      <div
        style={{ color: menuItemColor }}
        onClick={() => {
          item.onClick?.();
          onSelect?.(item);
        }}
      >
        {item.label}
      </div>
    ),
  }));

  return (
    <Dropdown
      menu={{ items: menuItems }}
      placement={Placement}
      trigger={['click']}
    >
      <div className={parentClassNames}>
        {buttonContent}
      </div>
    </Dropdown>
  );
}
