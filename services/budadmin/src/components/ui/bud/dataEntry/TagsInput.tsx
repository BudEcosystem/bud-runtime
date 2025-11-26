import React, { useContext, useEffect, useRef, useState } from "react";
import { Form, FormRule, Image } from "antd";
import { BudFormContext } from "../context/BudFormContext";
import { Text_12_300_EEEEEE, Text_12_400_808080 } from "../../text";
import { components, MenuPlacement } from "react-select";
import CreatableSelect from "react-select/creatable";
import {
  colourOptions,
  colourStyles,
  getChromeColor,
  randomColor,
} from "./TagsInputData";
import { Cross1Icon } from "@radix-ui/react-icons";
import CustomPopover from "src/flows/components/customPopover";
import FloatLabel from "./FloatLabel";
import InfoLabel from "./InfoLabel";

export type Tag = {
  name: string;
  color: string;
};

interface SelectProps {
  name: string;
  placeholder: string;
  defaultValue?: Tag[];
  rules: FormRule[];
  ClassNames?: string;
  SelectClassNames?: string;
  info: string;
  overrides?: any;
  onChange?: (value: Tag[]) => void;
  label: string;
  options: Tag[];
  required?: boolean;
  menuplacement?: MenuPlacement;
}

export default function TagsInput(props: SelectProps) {
  // Usage of DebounceSelect
  const [onTouched, setOnTouched] = useState(false);
  const { name: fieldName, options, required } = props;
  const { form } = useContext(BudFormContext);
  const [selected, setSelected] = useState<Tag[]>(props.defaultValue || []);
  const [inputValue, setInputValue] = useState("");
  const ref = React.useRef(null);
  // Track if we're updating from internal changes to prevent infinite loops
  const isInternalUpdate = useRef(false);
  // Ref to hold current selected for comparison without adding to dependencies
  const selectedRef = useRef(selected);
  selectedRef.current = selected;

  useEffect(() => {
    const element = document.getElementById("next-button");
    if (element) {
      element.addEventListener("click", () => {
        setOnTouched(true);
        form.validateFields([fieldName]);
      });
    }
    return () => {
      if (element) {
        element.removeEventListener("click", () => {
          setOnTouched(true);
          form.validateFields([fieldName]);
        });
      }
    };
  }, []);

  useEffect(() => {
    const updated: Tag[] = selected?.map((item) => ({
      name: item.name,
      color: item.color,
    }));
    form &&
      form.setFieldsValue &&
      form.setFieldsValue({
        [fieldName]: updated,
      });
    // Set flag before calling onChange to prevent the defaultValue sync from triggering
    isInternalUpdate.current = true;
    props.onChange && props.onChange(updated);
    // Reset flag after a tick to allow future external updates
    setTimeout(() => {
      isInternalUpdate.current = false;
    }, 0);
  }, [selected]);

  const handleCreate = (inputValue) => {
    try {
      // check if tag already exists
      const tagExists = options.find((tag) => tag.name === inputValue);

      let newOption: Tag;
      if (tagExists) {
        newOption = tagExists;
      } else {
        const color = randomColor();
        newOption = {
          name: inputValue,
          color: color.value,
        };
      }
      // setOptions([...options, newOption]);
      setSelected([...selected, newOption]);
      return newOption;
    } catch (error) {
      console.error("Error", error);
    }
  };

  useEffect(() => {
    // Skip if this is triggered by our own onChange callback
    if (isInternalUpdate.current) {
      return;
    }

    if (props.defaultValue) {
      // Compare by tag names to avoid infinite loops from array reference changes
      // Use ref to get current selected without adding it as a dependency
      const currentSelected = selectedRef.current;
      const selectedNames = currentSelected.map(t => t.name).sort().join(',');
      const defaultNames = props.defaultValue.map(t => t.name).sort().join(',');

      // Only update if the tags are actually different
      if (selectedNames !== defaultNames) {
        setSelected(props.defaultValue);
      }
    }
  }, [props.defaultValue]);

  return (
    <Form.Item
      // help={false}
      hasFeedback
      initialValue={props.defaultValue || []}
      name={fieldName}
      className={`floating-textarea flex items-center !rounded-[6px] relative !bg-[transparent] w-full mb-[.35rem] ${props.ClassNames}`}
      rules={props.rules}
    >
      <FloatLabel
        label={
          <InfoLabel
            text={props.label}
            content={props.info}
            required={props.required}
          />
        }
      >
        <CreatableSelect
          menuPlacement={props.menuplacement || "auto"}
          ref={ref}
          className={`drawerSelect w-full placeholder:text-xs text-xs  text-[#EEEEEE] indent-[.5rem]  placeholder:text-[#808080] font-light outline-none !bg-[transparent] rounded-[6px] hover:!bg-[#FFFFFF08] ${props.SelectClassNames}`}
          closeMenuOnSelect={false}
          isMulti
          styles={colourStyles(props.overrides)}
          // menuIsOpen={true}
          options={options?.map((tag) => ({
            label: tag.name,
            value: tag.color,
          }))}
          value={selected?.map((item) => ({
            label: item.name,
            value: item.color,
          }))}
          onChange={(newValue) => {
            setSelected(
              newValue.map((item) => ({
                name: item.label,
                color: item.value,
              })),
            );
          }}
          onBlur={() => {
            setOnTouched(true);
            form.validateFields([fieldName]);
          }}
          placeholder={props.placeholder}
          onKeyDown={(e: any) => {
            if (e.key === "Enter" && !ref.current.state.focusedOption) {
              e.preventDefault();
              return;
            }
            if (e.key === "Backspace" && e.target.value === "") {
              setSelected(selected.slice(0, selected.length - 1));
            }
            if (e.key === "Enter" && e.target.value) {
              handleCreate(e.target.value);
              setInputValue("");
            }
            form.validateFields([fieldName]);
          }}
          inputValue={inputValue}
          onInputChange={(value) => {
            setInputValue(value);
            form.validateFields([fieldName]);
          }}
          onCreateOption={handleCreate}
          components={{
            DropdownIndicator:
              required && onTouched && selected.length === 0
                ? () => (
                  <Image
                    preview={false}
                    className="absolute right-[.5rem] cursor-pointer"
                    src="/icons/warning.svg"
                    alt="error"
                    width={"1rem"}
                    height={"1rem"}
                  />
                )
                : null,
            MenuList: (props) => {
              return (
                <components.MenuList {...props}>
                  <Text_12_400_808080
                    style={{
                      marginBottom: "16px",
                    }}
                  >
                    Select an option or create one
                  </Text_12_400_808080>
                  {props.children}
                </components.MenuList>
              );
            },
            Option: (props) => {
              const { innerProps, innerRef } = props;
              // If color is not available, set it default bg color
              const color =
                colourOptions.find((option) => option.value === props.data.value)
                  ?.value || "#FFF";
              const selectedTag = selected?.find(
                (tag) => tag.name === props.data.label,
              );

              const handleOptionClick = (e: React.MouseEvent<HTMLDivElement>) => {
                if (selectedTag) {
                  // Tag is already selected, deselect it
                  e.stopPropagation();
                  setSelected(
                    selected.filter(
                      (item) => item.name !== props.data.label,
                    ),
                  );
                } else {
                  // Tag is not selected, select it via react-select's handler
                  if (innerProps.onClick) {
                    innerProps.onClick(e);
                  }
                }
              };

              return (
                <div
                  {...innerProps}
                  ref={innerRef}
                  onClick={handleOptionClick}
                  className="flex items-center justify-between cursor-pointer mb-1 py-[.3rem] px-[.3rem] hover:bg-[#1F1F1F] rounded-[8px]"
                  style={{
                    backgroundColor: props.isFocused ? "#1F1F1F" : "transparent",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                    }}
                  >
                    <div
                      style={{
                        backgroundColor: getChromeColor(color),
                        borderRadius: 8,
                        marginRight: 8,
                        color: color,
                        padding: "4px 8px",
                        gap: "6px",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      {props.data.label}
                      <button type="button" className="!text-[#B3B3B3] ">
                        {selectedTag && (
                          <Cross1Icon
                            className="!text-[#B3B3B3] colorFix"
                            style={{
                              width: ".75rem",
                              height: ".75rem",
                              color: "#B3B3B3 !important",
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
      </FloatLabel>
    </Form.Item>
  );
}
