import React, { useContext, useState } from "react";
import { ConfigProvider, Form, Switch } from "antd";
import FloatLabel from "./FloatLabel";
import InfoLabel from "./InfoLabel";
import { BudFormContext } from "../context/BudFormContext";

interface BudSwitchProps {
  name: string;
  label: string;
  infoText: string;
  placeholder: string;
  classNames?: string;
  labelClass?: string;
  defaultValue?: any;
  onChange?: any;
  rules?: any[];
  formItemClassnames?: string;
}

export default function BudSwitch(props: BudSwitchProps) {
  const [focus, setFocus] = useState(false);
  const { values, form } = useContext(BudFormContext);

  return (
    <Form.Item
      name={props.name}
      rules={props.rules}
      hasFeedback
      className={`${props.formItemClassnames}`}
    >
      <div className="flex justify-between gap-2">
        <div
          className={`float-label`}
          onBlur={() => setFocus(false)}
          onFocus={() => setFocus(true)}
        >
          <label
            className={`text-nowrap ${props.labelClass} ${props.classNames}`}
          >
            <InfoLabel
              text={props.label}
              content={props.infoText || props.placeholder}
            />
          </label>
        </div>
        <ConfigProvider
          theme={{
            token: {
              colorPrimary: "#965CDE",
            },
            components: {
              Switch: {
                // handleBg: '#965CDE',
              },
            },
          }}
        >
          <Switch
            defaultChecked={props.defaultValue}
            onChange={(value) => {
              form.setFieldsValue({ [props.name]: value });
              form.validateFields([props.name]);
              props.onChange && props.onChange(value);
            }}
          />
        </ConfigProvider>
      </div>
    </Form.Item>
  );
}
