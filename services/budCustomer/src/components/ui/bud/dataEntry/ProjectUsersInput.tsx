import React, { useCallback, useContext, useEffect, useState } from "react";
import { Avatar, Form, FormRule, Select, Image, Space } from "antd";
import { axiosInstance } from "@/services/api/requests";
import { BudFormContext } from "../context/BudFormContext";
import { Text_12_300_EEEEEE, Text_12_400_EEEEEE } from "../../text";
import CreatableSelect from "../../../../../node_modules/react-select/creatable/dist";
import {
  colourOptions,
  colourStyles,
  getChromeColor,
  randomColor,
} from "./TagsInputData";
import { Cross1Icon } from "@radix-ui/react-icons";
import { components } from "../../../../../node_modules/react-select/dist";
import CustomPopover from "@/flows/components/customPopover";
import { errorToast } from "@/components/toast";
import CustomDropDown from "@/flows/components/CustomDropDown";
import { useUsers, User } from "@/hooks/useUsers";

interface SelectProps {
  name: string;
  placeholder: string;
  defaultValue?: string;
  classNames?: string;
  rules: FormRule[];
  onChangeScope?: (selectedScope: string) => void;
}

export default function ProjectUsersInput(props: SelectProps) {
  // Usage of DebounceSelect
  const { users, getUsers } = useUsers();
  const { name: fieldName } = props;
  const { form } = useContext(BudFormContext);
  const [options, setOptions] = useState<(User & { label: string; value: string })[]>([]);
  const [scopes, setScopes] = useState("endpoint:view");
  const ref = React.useRef<any>(null);

  const scopeOptions = [
    {
      key: "endpoint:manage",
      label: "Manage",
      value: "endpoint:manage",
      onClick: async () => {
        setScopes("endpoint:manage");
        props.onChangeScope?.("endpoint:manage");
      },
    },
    {
      key: "endpoint:view",
      label: "View",
      value: "endpoint:view",
      onClick: async () => {
        setScopes("endpoint:view");
        props.onChangeScope?.("endpoint:view");
      },
    },
  ];

  const DropdownButtonContent = ({ scope }: { scope: string }) => {
    if (scope == "endpoint:view") {
      return <Text_12_400_EEEEEE>View</Text_12_400_EEEEEE>;
    }
    if (scope == "endpoint:manage") {
      return <Text_12_400_EEEEEE>Manage</Text_12_400_EEEEEE>;
    }
  };

  const [search, setSearch] = useState("");


  const load = useCallback(async () => {
    await getUsers({
      page: 1,
      limit: 10000,
      search: false,
    });
  }, []);

  useEffect(() => {
    load();
  }, [getUsers]);

  useEffect(() => {
    const data = users?.map((result) => ({
      ...result,
      label: result.name,
      value: result.id,
    }));
    setOptions(data);
  }, [users]);

  const selected = form.getFieldValue(fieldName);

  return (
    <Form.Item
      hasFeedback
      name={fieldName}
      className={`flex items-center rounded-[6px] relative !bg-[transparent] w-full mt-[.6rem] py-[0] ${props.classNames}`}
      rules={props.rules}
    >
      <div className="w-full">
        <Text_12_300_EEEEEE className="absolute px-[.7rem] bg-[#101010] -top-1.5 left-1.5 tracking-[.035rem] z-10 flex items-center gap-[.4rem]">
          Invite
          <CustomPopover
            title={
              "Invite teammates to collaborate. Or skip it if you’re flying solo!"
            }
          >
            <Image
              preview={false}
              src="/images/info.png"
              alt="info"
              style={{ width: ".75rem" }}
            />
          </CustomPopover>
        </Text_12_300_EEEEEE>
      </div>
      <CreatableSelect
        className={`drawerSelect w-full placeholder:text-xs text-xs  text-[#EEEEEE]  placeholder:text-[#808080] font-light outline-none !bg-[transparent] rounded-[6px] hover:!bg-[#FFFFFF08]`}
        ref={ref}
        isMulti
        options={options}
        openMenuOnFocus
        openMenuOnClick
        // menuIsOpen={true}
        value={form.getFieldValue(fieldName)}
        placeholder={props.placeholder}
        filterOption={(option, inputValue) => {
          if (!inputValue) return true; // Show all options if no input
          const searchText = inputValue.toLowerCase();
          return (
            option.label.toLowerCase().includes(searchText) || // Match label (name)
            (option as any).email?.toLowerCase().includes(searchText) // Match email
          );
        }}
        styles={{
          ...colourStyles(),
          menu: (provided) => ({
            ...provided,
            maxHeight: "110px", // Adjust this value to your desired height
            overflowY: "auto",
            background: "#161616",
            backdropFilter: "blur(4px)",
            padding: ".5rem",
            borderRadius: "6px",
            zIndex: "10000",
          }),
          menuList: () => ({
            maxHeight: "110px", // This controls the height of the items container
          }),
        }}
        onChange={(newValue) => {
          form.setFieldsValue({
            [fieldName]: newValue.map((item) => ({
              ...item,
              scopes: [scopes],
            })),
          });
        }}
        onCreateOption={(inputValue) => {
          try {
            // regex to check if email is valid
            const emailRegex =
              /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
            if (!emailRegex.test(inputValue)) {
              errorToast("Please enter a valid email address");
              if (ref.current?.select) {
                ref.current.select.clearValue();
                ref.current.select.focus();
              }
              return;
            }

            const color = randomColor();
            const newOption = {
              id: `temp-${Date.now()}`,
              name: inputValue,
              email: inputValue,
              label: inputValue,
              value: color.value,
              color: color.value,
              scopes: [scopes],
            };
            setOptions([...options, newOption]);
            form.setFieldsValue({
              [fieldName]: [...selected, newOption],
            });
            return newOption;
          } catch (error) {
            console.error("Error", error);
          }
        }}
        components={{
          Control: (props) => {
            const Co = components.Control;
            return (
              <div className="custom-select flex items-center justify-between border-[#757575] hover:border-[#CFCFCF] border rounded-[6px] bg-[#1F1F1F] px-2  bg-[transparent]">
                <Co {...props} className="border-none w-[100%]" />
                {/* <Select
                  variant="borderless"
                  style={{ maxWidth: 90 }}
                  className="text-[#EEEEEE] placeholder:text-[#808080] font-[400] !text-[.75rem] leading-[100%] outline-none !bg-[#1F1F1F] rounded-[6px] min-w-[100px] 1680px:min-w-[140px]"
                  options={scopeOptions}
                  value={scopes}
                  onChange={(newValue) => {
                    setScopes(newValue);
                  }}
                /> */}
                <CustomDropDown
                  items={scopeOptions}
                  Placement="bottomRight"
                  menuItemColor="#EEEEEE"
                  parentClassNames="text-[#EEEEEE] placeholder:text-[#808080] font-[400] !text-[.75rem] leading-[100%] outline-none !bg-[#1F1F1F] rounded-[6px] w-auto py-[.565rem] pl-[.8rem] pr-[.3rem]"
                  buttonContent={
                    <Space>
                      <DropdownButtonContent scope={scopes} />
                      <div className="w-[0.625rem] h-[0.625rem] flex justify-center items-center mr-[.3rem]">
                        <Image
                          preview={false}
                          src="/images/drawer/down.png"
                          alt="info"
                          style={{ width: "0.5rem" }}
                        />
                      </div>
                    </Space>
                  }
                />
              </div>
            );
          },
          MultiValueContainer: (props) => {
            const { innerProps } = props;
            return (
              <div
                {...innerProps}
                className="flex items-center justify-between cursor-pointer "
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                  }}
                >
                  <div
                    style={{
                      backgroundColor: getChromeColor("#FFFFFF08"),
                      borderRadius: 6,
                      marginRight: 6,
                      marginBottom: 6,
                      color: "#FFF",
                      padding: "4px 8px",
                      gap: "6px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <Avatar
                      size={20}
                      className="mr-1 p-[.3rem] text-[.7rem] w-[1.25rem] h-[1.25rem]"
                    >
                      {props.data.label?.[0]?.toUpperCase()}
                    </Avatar>
                    <span>{props.data.label}</span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        form.setFieldsValue({
                          [fieldName]: selected.filter(
                            (item: any) => item.label !== props.data.label
                          ),
                        });
                      }}
                    >
                      <svg
                        width="18"
                        height="18"
                        viewBox="0 0 18 18"
                        fill="none"
                        xmlns="http://www.w3.org/2000/svg"
                        className="hover:text-[#FFFFFF] mr-.5"
                      >
                        <path
                          fillRule="evenodd"
                          clipRule="evenodd"
                          d="M13.8103 5.09188C14.0601 4.8421 14.0601 4.43712 13.8103 4.18734C13.5606 3.93755 13.1556 3.93755 12.9058 4.18734L8.99884 8.0943L5.09188 4.18734C4.8421 3.93755 4.43712 3.93755 4.18734 4.18734C3.93755 4.43712 3.93755 4.8421 4.18734 5.09188L8.0943 8.99884L4.18734 12.9058C3.93755 13.1556 3.93755 13.5606 4.18734 13.8103C4.43712 14.0601 4.8421 14.0601 5.09188 13.8103L8.99884 9.90338L12.9058 13.8103C13.1556 14.0601 13.5606 14.0601 13.8103 13.8103C14.0601 13.5606 14.0601 13.1556 13.8103 12.9058L9.90338 8.99884L13.8103 5.09188Z"
                          fill="#B3B3B3"
                        />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            );
          },
          Option: (props) => {
            const { innerProps, innerRef } = props;
            // If color is not available, set it default bg color
            const color =
              colourOptions.find((option) => option.value === props.data.value)
                ?.value || "#FFF";
            const selectedTag = selected?.find(
              (tag: any) => tag.label === props.data.label
            );
            return (
              <div
                {...innerProps}
                ref={innerRef}
                className="flex items-center justify-between cursor-pointer mb-1 py-[.3rem] px-[.3rem] hover:bg-[#1F1F1F] rounded-[6px] z-[1200] relative"
                style={{
                  backgroundColor: props.isFocused ? "#1F1F1F" : "transparent",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    width: "100%",
                  }}
                  onClick={(e) => {
                    if (selectedTag) {
                      e.stopPropagation();
                      form.setFieldsValue({
                        [fieldName]: selected.filter(
                          (item: any) => item.label !== props.data.label
                        ),
                      });
                    }
                  }}
                >
                  <div
                    style={{
                      borderRadius: 6,
                      marginRight: 8,
                      color: color,
                      padding: "4px 8px",
                      gap: "6px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: "100%",
                      WebkitJustifyContent: "flex-start",
                    }}
                    className="hover:bg-[#1F1F1F]"
                  >
                    <Avatar
                      size={20}
                      className="mr-1 p-[.3rem] text-[.7rem] w-[1.25rem] h-[1.25rem]"
                    >
                      {props.data.label?.[0]?.toUpperCase()}
                    </Avatar>
                    <span>{props.data.label}</span>
                    <button type="button" className="text-[#B3B3B3] ">
                      {selectedTag && (
                        <Cross1Icon
                          style={{
                            width: "10px",
                            height: "10px",
                          }}
                        />
                      )}
                    </button>
                  </div>
                </div>
              </div>
            );
          },
        }}
      />
    </Form.Item>
  );
}
