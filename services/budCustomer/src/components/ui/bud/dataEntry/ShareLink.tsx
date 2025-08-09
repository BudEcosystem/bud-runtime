import React, { useContext } from "react";
import { Form, FormRule, Select } from "antd";
import { GlobeIcon, Link2Icon } from "lucide-react";
import { SecondaryButton } from "../form/Buttons";
import { BudFormContext } from "../context/BudFormContext";

const ShareLink: React.FC<{
  placeholder: string;
  rules: FormRule[];
}> = (props) => {
  const { form } = useContext(BudFormContext);
  return (
    <div className="flex flex-row items-center justify-between pt-[0rem] pb-[.5rem]">
      <div className="flex items-center">
        <GlobeIcon size={16} className="text-[#B3B3B3] mr-2" />
        <span className="text-[#B3B3B3] font-[400] text-[.75rem]">
          Anyone with the link can
        </span>
        <Form.Item
          hasFeedback
          name="publicShareMode"
          initialValue="View"
          rules={props.rules}
          className="mb-[0]"
        >
          <Select
            // open={true}
            variant="borderless"
            placeholder={props.placeholder}
            className="mb-[0] text-[#B3B3B3]"
            popupClassName="bg-[#1F1F1F] border-[#1F1F1F] border-0 text-[#B3B3B3]"
            maxTagCount={"responsive"}
            options={[
              { label: "View", value: "View" },
              { label: "Edit", value: "Edit" },
              { label: "Comment", value: "Comment" },
            ]}
          />
        </Form.Item>
      </div>
      <div>
        <SecondaryButton classNames="!border-[transparent] px-[.6rem]">
          <div className="flex items-center gap-1">
            <Link2Icon
              size={12}
              className="text-[#B3B3B3] rotate-[-45deg] mr-[.2rem]"
            />
            <div className="text-[.75rem] text-[#B3B3B3] font-[400]">
              Copy Link
            </div>
          </div>
        </SecondaryButton>
      </div>
    </div>
  );
};

export default ShareLink;
