import React, { useEffect, useRef, useState } from 'react';
import { PlusOutlined } from '@ant-design/icons';
import { Button, Divider, Input, Select, Space } from 'antd';
import type { InputRef } from 'antd';

interface SelectWithAddProps {
    options: any[];
    defaultValue: any;
    onChange: (value: any) => void;
    onAdd: (value: any) => void;
}

export default function SelectWithAdd(props: SelectWithAddProps) {
    const [options, setOptions] = useState(props.options);
    const [selected, setSelected] = useState("");
    const inputRef = useRef<InputRef>(null);

    useEffect(() => {
        setOptions(props.options);
    }, [props.options]);

    const onChange = (value: any) => {
        props.onChange(value);
    }

    return (
        <Select
            placeholder="Select preset"
            defaultValue={props.defaultValue}
            popupRender={(menu) => (
                <>
                    {menu}
                    <Divider style={{ margin: '8px 0' }} />
                    <Space style={{ padding: '0 8px 4px' }}>
                        <Input
                            placeholder="Please enter item"
                            ref={inputRef}
                            value={selected}
                            onChange={(e) => setSelected(e.target.value)}
                            onKeyDown={(e) => e.stopPropagation()}
                        />
                        <Button type="primary" icon={<PlusOutlined />} onClick={() => props.onAdd(selected)}>
                            Add
                        </Button>
                    </Space>
                </>
            )}
            options={options.map((item) => ({ label: item.name, value: item.id }))}
            onChange={onChange}
            className='agentSelect'
        />
    );
}
