import { Button, Form, Image, Input, Popover } from "antd";
import EmojiPicker, { Categories, EmojiStyle, Theme } from "emoji-picker-react";
import React, { useContext, useEffect } from "react";
import { BudFormContext } from "../context/BudFormContext";
import { pxToRem, Text_26_600_FFFFFF } from "../../text";
import { assetBaseUrl } from "@/components/environment";
import { Pencil1Icon } from "@radix-ui/react-icons";
import { modelNameRegex, projectNameRegex } from "@/lib/utils";
import IconRender from "src/flows/components/BudIconRender";

interface Props {
  placeholder: string;
  onChangeIcon?: (value: string) => void;
  isEdit?: boolean;
}


export function NameIconDisplay({
  name,
  icon,
}: {
  name: string;
  icon: string;
}) {
  return (
    <div className="drawerNameInput flex flex-row items-center justify-between">
      <Button
        className="text-2xl items-center flex justify-center  rounded-[0.25rem] h-[2.1875rem] w-[2.1875rem]  bg-[#1F1F1F] p-1 mr-[0.5rem]"
        type="link"
      >
        <div>{icon}</div>
      </Button>
      <div className="w-full" >
        <div
          className="pl-1 rounded-[6px] !bg-transparent text-[#EEEEEE] placeholder-[#808080] !border-none outline-0 text-xl w-full h-10 border-transparent focus:border-transparent focus:ring-0 h-full"
          style={{ outline: 'none', border: 'none' }}
        >
          <Text_26_600_FFFFFF className="text-[#EEEEEE]">{name}</Text_26_600_FFFFFF>
        </div>
      </div>
    </div>
  )
}

export function NameImageDisplay({
  name,
  icon,
  editable,
  onChangeIcon,
}: {
  name: string;
  icon: string;
  editable?: boolean;
  onChangeIcon?: (value: string) => void;
}) {
  const imageUrl = assetBaseUrl + (icon)
  return (
    <div className="drawerNameInput flex flex-row items-center justify-between">
      <Button
        className="text-2xl items-center flex jutify-center  rounded-[0.25rem] h-[2.25rem] w-[2.25rem]  bg-[#1F1F1F] p-1 mr-[0.5rem]"
        type="link"
      >
        <Image
          preview={false}
          src={imageUrl}
          alt="info"
          style={{ width: '1.5rem', height: '1.5rem' }}
        />
        {editable && <div
          onClick={() => onChangeIcon && onChangeIcon(icon)}
          className="absolute top-[-0.5rem] right-[-0.5rem] p-1 bg-[#1F1F1F] rounded-full">
          <svg width="0.625rem" height="0.625rem" viewBox="0 0 10 10" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path fillRule="evenodd" clipRule="evenodd" d="M7.90401 0.7656C7.77383 0.635425 7.56278 0.635425 7.4326 0.7656L2.47799 5.72021C2.41802 5.78018 2.37004 5.85104 2.33664 5.929L1.36192 8.20333C1.30823 8.32861 1.33622 8.47396 1.4326 8.57034C1.52898 8.66672 1.67433 8.69471 1.79961 8.64102L4.07394 7.6663C4.1519 7.6329 4.22276 7.58492 4.28273 7.52495L9.23734 2.57034C9.36751 2.44016 9.36751 2.22911 9.23734 2.09893L7.90401 0.7656ZM2.9494 6.19161L7.6683 1.47271L8.53023 2.33464L3.81133 7.05354L2.81477 7.48064L2.5223 7.18817L2.9494 6.19161Z" fill="#B3B3B3" />
          </svg>
        </div>}
      </Button>
      <div className="w-full" >
        <div
          className="pl-1 rounded-[6px] !bg-transparent text-[#EEEEEE] placeholder-[#808080] !border-none outline-0 text-xl w-full h-10 border-transparent focus:border-transparent focus:ring-0 h-full"
          style={{ outline: 'none', border: 'none' }}
        >
          <Text_26_600_FFFFFF className="text-[#EEEEEE]">{name}</Text_26_600_FFFFFF>
        </div>
      </div>
    </div>
  )
}



export function ModelNameInput({
  placeholder,
  onChange,
  icon,
  type,
}: {
  placeholder: string;
  onChange?: (value: string) => void;
  icon: string;
  type?: string;
}) {
  const { form } = useContext(BudFormContext);
  const name = form.getFieldValue("name");

  useEffect(() => {
    onChange && onChange(name);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [icon, name]);
  return (
    <div className="drawerNameInput flex flex-row items-start justify-between mb-[1rem]">

      <Form.Item
        name={"icon"}
        className="relative mr-[.3rem]"
      >
        <div className="h-[2.25rem]">
          {type == "huggingface" ? (
            <div className=" bg-[#1F1F1F] rounded-[.4rem]  flex items-center justify-center"
              style={{ width: pxToRem(36), height: pxToRem(36), minWidth: pxToRem(36), maxWidth: pxToRem(36), minHeight: pxToRem(36), maxHeight: pxToRem(36) }}
            >
              <Image
                preview={false}
                src="/images/drawer/huggingface.png"
                alt="info"
                style={{ width: pxToRem(18), height: pxToRem(18) }}
              />
            </div>
          ) : (
            <IconRender
              icon={icon}
              size={36}
            />
          )}
        </div>
      </Form.Item>
      <Form.Item
        hasFeedback
        name={"name"}
        // className="w-full pb-0 mb-[0]"
        className="w-full pb-0 mb-[0] justify-center nameBorder"
        rules={[
          {
            required: true,
            message: `Please ${placeholder}`,
          },
          {
            pattern: modelNameRegex,
            message: "Model name should contain only alphanumeric characters",
          }
        ]}
      >
        <Input
          className="pl-2 rounded-[6px] !bg-transparent text-[#EEEEEE] placeholder-[#808080] !border-none outline-0 text-xl w-full border-transparent focus:border-transparent focus:ring-0"
          style={{ outline: 'none', border: 'none' }}
          type="text"
          placeholder={placeholder}
        />
      </Form.Item>
    </div>
  );
}

export function NameIconInput({
  placeholder,
  icon,
  onChangeIcon,
  disabled,
  isEdit
}: {
  placeholder: string;
  icon: string;
  onChangeIcon?: (value: string) => void;
  disabled?: boolean;
  isEdit?: boolean;
}) {
  return (
    <div className="drawerNameInput flex flex-row items-center justify-between  mb-[1rem]">
      <Form.Item
        name={"icon"}
        rules={[
          {
            required: false,
            message: "",
          },
        ]}
        className="relative"
      >
        {isEdit && (
          <div className="absolute group w-[1.125rem] h-[1.125rem] flex justify-center items-center border-none hover:border-transparent top-[-.45rem] right-[0] z-[1200] rounded-full bg-[#1F1F1F] cursor-pointer">
            <Pencil1Icon className="w-[0.625rem] h-[0.625rem] text-[#5B6168] group-hover:text-[#FFFFFF] text-[0.875em]" />
          </div>
        )}
        <Popover
          trigger={"click"}
          open={disabled ? false : undefined}
          content={
            <EmojiPicker
              theme={Theme.DARK}
              style={{ backgroundColor: "#161616" }}
              emojiVersion="1.0"
              skinTonesDisabled
              previewConfig={{
                showPreview: false,
              }}
              className=" p-2 max-h-[350px]"
              onEmojiClick={(emojiObject) => {
                onChangeIcon && onChangeIcon(emojiObject.emoji);
              }}
              emojiStyle={EmojiStyle.GOOGLE}
              categories={[
                {
                  category: Categories.SUGGESTED,
                  name: 'Recently Used'
                },
                {
                  category: Categories.CUSTOM,
                  name: 'Custom'
                },
                {
                  category: Categories.TRAVEL_PLACES,
                  name: 'Travel & Places'
                },
                {
                  category: Categories.ACTIVITIES,
                  name: 'Activities'
                },
                {
                  category: Categories.OBJECTS,
                  name: 'Objects'
                },
                {
                  category: Categories.SYMBOLS,
                  name: 'Symbols'
                },
                {
                  category: Categories.FLAGS,
                  name: 'Flags'
                },
              ]}
            />
          }
        >
          <Button
            className="text-2xl items-center flex jutify-center  rounded-[4px] h-[2.25rem] w-[2.25rem]  bg-[#35341B] p-1 mr-[0.5rem]"
            type="link"
          >
            {icon}
          </Button>
        </Popover>
      </Form.Item>
      <Form.Item
        hasFeedback
        name={"name"}
        validateFirst
        // className="w-full"
        className="w-full border-[1px] border-[#757575] box-border rounded-[6px] justify-center"
        rules={[
          {
            required: true,
            message: `Please ${placeholder}`,
          },
          {
            max: 30,
            message: `${placeholder} should be less than 30 characters`,
          },
          {
            pattern: projectNameRegex,
            message: `${placeholder} should contain only alphanumeric characters`,
          }
        ]}
      >
        <Input
          className="pl-2 rounded-[6px] !bg-transparent text-[#EEEEEE] placeholder-[#808080] !border-none outline-0 text-xl w-full border-transparent focus:border-transparent focus:ring-0"
          style={{ outline: 'none', border: 'none' }}
          type="text"
          placeholder={placeholder}
          disabled={disabled}
        />
      </Form.Item>
    </div>
  )
}

export default function ProjectNameInput({
  placeholder,
  onChangeIcon,
  isEdit
}: Props) {
  const { form } = useContext(BudFormContext);
  const icon = form.getFieldValue("icon");

  return (
    <NameIconInput
      placeholder={placeholder}
      icon={icon}
      onChangeIcon={(emoji) => {
        form.setFieldsValue({ icon: emoji });
        onChangeIcon && onChangeIcon(emoji);
      }}
      disabled={false}
      isEdit={isEdit}
    />
  );
}
