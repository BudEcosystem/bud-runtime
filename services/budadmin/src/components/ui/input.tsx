import * as React from "react";
import { Box, Button, Flex, TextArea, TextField, Text } from "@radix-ui/themes";
import * as Select from "@radix-ui/react-select";
import * as Switch from "@radix-ui/react-switch";
import * as Slider from "@radix-ui/react-slider";
import { CaretDownIcon, Cross1Icon, FilePlusIcon } from "@radix-ui/react-icons";
import classNames from "classnames";
import { useState } from "react";
import * as Checkbox from "@radix-ui/react-checkbox";
import { CheckIcon } from "@radix-ui/react-icons";

import {
  Text_12_300_44474D,
  Text_12_400_787B83,
  Text_12_400_808080,
  Text_12_400_FFFFFF,
} from "./text";

// checkbox input wraper
interface CheckBoxInputProps {
  className?: string;
  indicatorClassName?: string;
  defaultCheck?: boolean;
  onCheckedChange?: (checked: boolean) => void;
  [key: string]: any;
}

const CheckBoxInput: React.FC<CheckBoxInputProps> = ({
  className,
  indicatorClassName,
  defaultCheck,
  checkedChange,
  onCheckedChange,
  ...props
}) => {
  const [internalChecked, setInternalChecked] = useState(defaultCheck ?? false);

  // Use controlled value if provided, otherwise use internal state
  const isChecked = checkedChange !== undefined ? checkedChange : internalChecked;

  const handleCheckedChange = (checked: boolean) => {
    setInternalChecked(checked);
    if (onCheckedChange) {
      onCheckedChange(checked);
    }
  };

  return (
    <Flex align="center">
      <Checkbox.Root
        className={classNames(
          `w-[0.875rem] h-[0.875rem] border border-[#757575] rounded-[0.25rem] hover:border-[#965CDE] hover:shadow-[0_0_1.9px_1px_rgba(150,92,222,0.6)]`,
          {
            "border-[#965CDE] !bg-[#965CDE]": isChecked, // Apply class when checked
            [className || ""]: className, // Apply any additional className passed as a prop
          },
        )}
        onCheckedChange={handleCheckedChange}
        checked={isChecked}
        {...props}
      >
        <Checkbox.Indicator
          className={classNames("flex items-center justify-center", {
            [indicatorClassName || ""]: indicatorClassName, // Apply additional indicator className
          })}
        >
          <CheckIcon className="text-[black] h-[100%]" />
        </Checkbox.Indicator>
      </Checkbox.Root>
      {/* <Text_12_400_808080 className="ml-[.45rem] tracking-[.01rem] cursor-pointer select-none">
        Remember me
      </Text_12_400_808080> */}
    </Flex>
  );
};

// slider input wraper
interface SliderInputProps {
  className?: string;
  classTrack?: any;
  classRange?: any;
  classThumb?: any;
  defaultValue?: any;
  [key: string]: any;
}
const SliderInput: React.FC<SliderInputProps> = ({
  className,
  classTrack,
  classRange,
  classThumb,
  defaultValue,
  ...props
}) => (
  <Slider.Root
    className={classNames(
      `budSlider relative block flex items-center select-none touch-none w-full border border-[#212225] !h-[0.725rem] max-h-[0.725rem] py-[.8rem] px-[.5rem] rounded-md ${className}`,
    )}
    {...props}
    defaultValue={defaultValue}
  >
    <Slider.Track
      className={`bg-[#212225] relative grow rounded-full h-[3px] ${classTrack}`}
    >
      <Slider.Range
        className={`absolute bg-[#965CDE] rounded-full h-full ${classRange}`}
      />
    </Slider.Track>
    <Slider.Thumb
      className={`block w-[8px] h-[8px] bg-white rounded-full cursor-pointer ${classThumb}`}
      aria-label="Volume"
    />
  </Slider.Root>
);

// switch input wraper
interface SwitchInputProps {
  className?: string;
  classNameRoot?: string;
  classNameThump?: string;
  disabled?: boolean;
  defaultCheck?: boolean;
  [key: string]: any;
}
const SwitchInput: React.FC<SwitchInputProps> = ({
  className,
  classNameRoot,
  classNameThump,
  defaultCheck,
  disabled = false,
  ...props
}) => (
  <Switch.Root
    disabled={disabled}
    className={`w-[1.4375rem] h-[0.725rem] bg-[#212225] rounded-full relative shadow-none p-[0rem] data-[state=checked]:bg-[#965CDE] outline-none cursor-default border border-[#181925] ${classNameRoot}`}
    {...props}
  >
    <Switch.Thumb
      className={`block w-[0.55rem] h-[0.55rem] bg-white rounded-full transition-transform duration-100 translate-x-0.5 will-change-transform data-[state=checked]:translate-x-[0.75rem] ${classNameThump}`}
    />
  </Switch.Root>
);

// text input wraper
interface TextInputProps {
  textFieldSlot?: any;
  className?: string;
  [key: string]: any;
}
const TextInput: React.FC<TextInputProps> = ({
  textFieldSlot,
  className,
  ...props
}) => (
  <TextField.Root
    maxLength={100}
    className={`w-full place max-w-[350px] text-[0.740625rem] font-light text-[#44474D] content-center outline-[.5px] outline-[white] rounded-md border border-[#212225] shadow-none leading-[100%] pt-[.2em] hover:border-[#63656c] ${className}`}
    {...props}
    style={{
      height: '1.75rem',
      background: 'transparent',
    }}
  >
    {textFieldSlot && textFieldSlot}
  </TextField.Root>
);

// textarea wraper
interface TextAreaInputProps {
  className?: string;
  [key: string]: any;
}
const TextAreaInput: React.FC<TextAreaInputProps> = ({
  className,
  ...props
}) => (
  <TextArea
    size="1"
    style={{
      fontSize: "0.740625rem",
      fontWeight: 400,
      color: '#44474D',
      maxWidth: '350px',
      minHeight: '50px',
      height: '1.75rem',
      backgroundColor: '#0f0f0f',
      outlineWidth: '.5px',
      outlineColor: 'white',
      borderWidth: '1px',
      borderColor: '#212225',
      paddingLeft: '0',
      paddingRight: '0',
     }}
    className={`w-full textArea rounded-md shadow-none hover:border-[#63656c] ${className}`}
    {...props}
  />
);

// select input wraper
interface SelectInputProps {
  size?: any;
  value?: any;
  onValueChange?: any;
  defaultValue?: any;
  className?: string;
  valueClassName?: string;
  placeholder?: string;
  selectItems?: any;
  renderItem?: any;
  showSearch?: boolean;
  [key: string]: any;
}
const SelectInput: React.FC<SelectInputProps> = ({
  size,
  value,
  defaultValue,
  onValueChange,
  className,
  valueClassName,
  placeholder,
  selectItems,
  renderItem,
  showSearch,
  ...props
}) => {
  const [isReady, setIsReady] = React.useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [isSearchVisible, setIsSearchVisible] = useState<boolean>(true);
  const [filteredItems, setFilteredItems] = useState(selectItems);

  const handleSearch = (event) => {
    const value = event?.target?.value?.toLowerCase();
    setSearchTerm(value);
    setFilteredItems(
      selectItems.filter((item) =>
        (renderItem ? renderItem(item) : item.label || item)
          ?.toLowerCase()
          ?.includes(value),
      ),
    );
  };

  React.useEffect(() => {
    setFilteredItems(selectItems);
  }, [selectItems]);

  React.useEffect(() => {
    if (showSearch != undefined) {
      setIsSearchVisible(showSearch);
    }
  }, [showSearch]);

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setIsReady(true);
    }, 500); // 0.5s delay

    return () => clearTimeout(timer);
  }, []);
  const [state, setState] = useState("closed");
  return (
    <Select.Root
      value={value}
      defaultValue={defaultValue}
      onValueChange={(newValue) => {
        onValueChange(newValue);
      }}
      {...(isReady ? props : {})}
      onOpenChange={(open) => {
        if (!open) {
          setSearchTerm("");
          setFilteredItems(selectItems);
        }
        setState(open ? "open" : "closed");
      }}
    >
      <Select.Trigger
        className={classNames(
          `w-full max-w-[350px] h-[1.75rem] px-[.3rem] outline-[.5px] outline-[white] rounded-md border border-[#212225] bg-transparent text-[#FFFFFF] data-[placeholder]:text-[#6A6E76] text-nowrap text-xs font-light outline-[white] cursor-pointer hover:border-[#63656c] ${className}`,
          {
            "border-[white]": state === "open",
          },
        )}
        // className={`w-full max-w-[350px] h-[1.75rem] px-[.3rem] outline-[.5px] outline-[white] rounded-md border border-[#212225] bg-transparent text-[white] data-[placeholder]:text-[#6A6E76] text-nowrap text-xs font-light cursor-pointer hover:border-[#63656c] ${className}`}
        disabled={selectItems?.length === 0}
        asChild={true}
      >
        <Flex justify="between" align="center" className="w-full">
          <Box className={`w-[100%] truncate text-left  ${valueClassName}`}>
            <Select.Value
              className={`text-white text-left text-nowrap text-[.1rem] font-light leading-[100%] truncate block ${valueClassName}`}
              placeholder={placeholder}
            >
              {value ? value : defaultValue ? defaultValue : placeholder}
            </Select.Value>
          </Box>
          <Select.Icon className="ml-0 text-[#6A6E76] block">
            <CaretDownIcon className="text-[1.5rem] w-[1.1rem] h-[1.1rem] text-[#ffffff]" />
          </Select.Icon>
        </Flex>
      </Select.Trigger>
      <Select.Portal>
        <Select.Content
          position="popper"
          className="SelectContentHeight bg-[#111113] text-xs text-[#FFFFFF] border border-[#212225] rounded-md p-[.5rem] box-border "
        >
          <Select.ScrollUpButton />
          <Select.Viewport className="w-full">
            {isSearchVisible && (
              <input
                placeholder="Search"
                className={`h-7 w-full placeholder:text-xs mb-2 text-xs text-[#EEEEEE] hover:bg-white hover:bg-opacity-[3%] placeholder:text-[#808080] font-light outline-none bg-transparent border border-[#212225] rounded-[5px] py-1 px-2.5`}
                type="text"
                value={searchTerm}
                onChange={handleSearch}
                onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) =>
                  e.stopPropagation()
                }
              />
            )}

            {filteredItems &&
              filteredItems.map((item, index) => (
                <Select.Item
                  className="h-[1.75rem] py-[.5rem] px-[.8rem] w-full hover:bg-[#18191B] rounded-md cursor-pointer border-none shadow-none outline-0 leading-[100%]"
                  key={index}
                  value={item}
                >
                  <Select.ItemText className="border-none shadow-none text-xs text-left text-[#FFFFFF] font-normal leading-[100%] truncate">
                    {renderItem ? renderItem(item) : item.label || item}
                  </Select.ItemText>
                </Select.Item>
              ))}
          </Select.Viewport>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  );
};

const SelectCustomInput: React.FC<SelectInputProps> = ({
  size,
  value,
  onValueChange,
  defaultValue,
  className,
  placeholder,
  selectItems,
  renderItem,
  showSearch,
  ...props
}) => {
  const [isReady, setIsReady] = React.useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [isSearchVisible, setIsSearchVisible] = useState<boolean>(true);
  const [filteredItems, setFilteredItems] = useState(selectItems);

  const handleSearch = (event) => {
    const value = event?.target?.value?.toLowerCase();
    setSearchTerm(value);
    setFilteredItems(
      selectItems.filter((item) =>
        (renderItem ? renderItem(item) : item.label || item)
          ?.toLowerCase()
          ?.includes(value),
      ),
    );
  };

  React.useEffect(() => {
    setFilteredItems(selectItems);
  }, [selectItems]);

  React.useEffect(() => {
    if (showSearch != undefined) {
      setIsSearchVisible(showSearch);
    }
  }, [showSearch]);

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setIsReady(true);
    }, 500); // 0.5s delay

    return () => clearTimeout(timer);
  }, []);
  const [state, setState] = useState("closed");
  return (
    <Select.Root
      defaultValue={defaultValue}
      value={value}
      onValueChange={(newValue) => {
        onValueChange(newValue);
      }}
      {...(isReady ? props : {})}
      onOpenChange={(open) => {
        if (!open) {
          setSearchTerm("");
          setFilteredItems(selectItems);
        }
        setState(open ? "open" : "closed");
      }}
    >
      <Select.Trigger
        className={classNames(
          `w-full max-w-[350px] h-[1.75rem] px-[.3rem] outline-[.5px] outline-[white] rounded-md border border-[#212225] bg-transparent text-[white] data-[placeholder]:text-[#6A6E76] text-nowrap text-xs font-light outline-[white] cursor-pointer hover:border-[#63656c] ${className}`,
          {
            "border-[white]": state === "open",
          },
        )}
        // className={`w-full max-w-[350px] h-[1.75rem] px-[.3rem] outline-[.5px] outline-[white] rounded-md border border-[#212225] bg-transparent text-[white] data-[placeholder]:text-[#6A6E76] text-nowrap text-xs font-light outline-[white] Active:border-[white] ${className}`}
        disabled={selectItems.length === 0}
        asChild={true}
      >
        <Flex justify="between" align="center" className="w-full">
          <Box className="w-[100%] truncate text-left">
            <Select.Value
              className="text-white text-left text-nowrap text-[.1rem] font-light leading-[100%] truncate block"
              placeholder={placeholder}
            >
              {value ? value : defaultValue ? defaultValue : placeholder}
            </Select.Value>
          </Box>
          <Select.Icon className="ml-0 text-[#6A6E76] block">
            <CaretDownIcon className="text-[1.5rem] w-[1.1rem] h-[1.1rem] text-[#ffffff]" />
          </Select.Icon>
        </Flex>
      </Select.Trigger>
      <Select.Portal>
        <Select.Content
          position="popper"
          className="content-contstrain bg-[#111113] text-xs text-[#FFFFFF] border border-[#212225] rounded-md p-[.5rem] box-border "
        >
          <Select.ScrollUpButton />
          <Select.Viewport className="w-full">
            {isSearchVisible && (
              <input
                placeholder="Search"
                className={`h-7 w-full placeholder:text-xs mb-2 text-xs text-[#EEEEEE] hover:bg-white hover:bg-opacity-[3%] placeholder:text-[#808080] font-light outline-none bg-transparent border border-[#212225] rounded-[5px] py-1 px-2.5`}
                type="text"
                value={searchTerm}
                onChange={handleSearch}
                onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) =>
                  e.stopPropagation()
                }
              />
            )}
            {filteredItems &&
              filteredItems.map((item, index) => (
                <Select.Item
                  className="h-[1.75rem] py-[.5rem] px-[.8rem] w-full hover:bg-[#18191B] rounded-md cursor-pointer border-none shadow-none outline-0 leading-[100%]"
                  key={index}
                  value={item}
                >
                  <Select.ItemText className="border-none shadow-none text-xs text-left text-[#FFFFFF] font-normal leading-[100%] truncate">
                    {renderItem ? renderItem(item) : item.label || item}
                  </Select.ItemText>
                </Select.Item>
              ))}
          </Select.Viewport>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  );
};

interface FileInputProps {
  className?: string;
  acceptedFileTypes: string[];
  maxFiles?: number;
  onFilesChange: (files: File[]) => void;
}

const FileInput: React.FC<FileInputProps> = ({
  className,
  acceptedFileTypes,
  maxFiles = 5,
  onFilesChange,
}) => {
  const [files, setFiles] = React.useState<File[]>([]);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const newFiles = Array.from(event.target.files || []);
    if (newFiles.length + files.length > maxFiles) {
      alert(`You can only upload up to ${maxFiles} files.`);
      return;
    }
    setFiles((prevFiles) => {
      const updatedFiles = [...prevFiles, ...newFiles];
      onFilesChange(updatedFiles);
      return updatedFiles;
    });
    event.target.value = ""; // Clear input value to prevent re-trigger
  };

  const handleRemoveFile = (
    index: number,
    e: React.MouseEvent<HTMLButtonElement>,
  ) => {
    e.stopPropagation(); // Prevent event bubbling
    e.preventDefault(); // Prevent default button action
    setFiles((prevFiles) => {
      const updatedFiles = prevFiles.filter((_, i) => i !== index);
      onFilesChange(updatedFiles);
      return updatedFiles;
    });
  };

  const handleClick = () => {
    if (inputRef.current) {
      inputRef.current.click();
    }
  };

  return (
    <div className={`file-input-component ${className}`}>
      {files.length < maxFiles && (
        <label className="pb-1 block">
          <input
            type="file"
            ref={inputRef}
            multiple
            accept={acceptedFileTypes.join(",")}
            onChange={handleFileChange}
            className="hidden"
          />
          <Button
            onClick={handleClick}
            size="1"
            className="flex rounded-md bg-transparent !border !border-dashed !border-[#44474D] text-left !py-[.8rem] items-center justify-start"
          >
            <FilePlusIcon className="text-[#44474D]" />
            <Text_12_300_44474D className="leading-full">
              Choose Files
            </Text_12_300_44474D>
          </Button>
        </label>
      )}
      {files.length > 0 && (
        <ul className="file-list mt-2">
          {files.map((file, index) => (
            <li
              key={index}
              className="file-item flex items-center justify-between mb-1"
            >
              <Text_12_400_FFFFFF className="block border border-[#212225] rounded-md px-[.7rem] py-[.4rem]">
                {file.name}
              </Text_12_400_FFFFFF>
              <button
                onClick={(e) => handleRemoveFile(index, e)}
                className="remove-file-btn ml-2"
              >
                <Cross1Icon className="text-red-500" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export {
  CheckBoxInput,
  TextInput,
  SelectInput,
  TextAreaInput,
  SwitchInput,
  SliderInput,
  FileInput,
  SelectCustomInput,
};

// add edit modal pop old

// import React, { useEffect } from 'react';
// import { Dialog, Button, Text, TextField, Select, Flex } from '@radix-ui/themes';
// import { Cross1Icon } from '@radix-ui/react-icons';
// import { Field } from './types'; // Import the Field type
// import {
//         Text_12_300_44474D,
//         Text_12_400_787B83,
//         Text_16_600_FFFFFF
//       } from '@/components/ui/text';

// interface CommonModalProps {
//   isOpen: boolean;
//   onOpenChange: (isOpen: boolean) => void;
//   title: string;
//   description: string;
//   fields: Field[];
//   initialValues?: { [key: string]: string }; // Optional initial values for edit functionality
//   onSubmit: (formData: { [key: string]: string }) => void;
// }

// const CommonModal: React.FC<CommonModalProps> = ({
//   isOpen,
//   onOpenChange,
//   title,
//   description,
//   fields,
//   initialValues = {}, // Default to empty object
//   onSubmit,
// }) => {
//   const [formData, setFormData] = React.useState<{ [key: string]: string }>({});
//   const [editFormData, setEditFormData] = React.useState<{ [key: string]: string }>({});

//   useEffect(() => {
//     if (isOpen) {
//       setFormData(initialValues); // Set form data to initial values when modal is opened
//       setEditFormData({}); // Reset editFormData
//     }
//   }, [isOpen, initialValues]);
//   const handleChange = (name: string, value: string) => {
//     setFormData((prev) => ({ ...prev, [name]: value }));
//     if (initialValues[name] !== value) {
//       handleEditChange(name, value);
//     } else {
//       handleEditChange(name, null); // Remove from editFormData if value is same as initial
//     }
//   };

//   const handleEditChange = (name: string, value: string | null) => {
//     setEditFormData((prev) => {
//       if (value === null) {
//         const { [name]: _, ...rest } = prev;
//         return rest;
//       }
//       return { ...prev, [name]: value };
//     });
//   };

//   const handleSubmit = () => {
//     onSubmit(Object.keys(editFormData).length ? editFormData : formData);
//   };

//   const textFields = fields.filter(field => field.type === 'text');
//   const selectFields = fields.filter(field => field.type === 'select');
//   const editFields = fields.filter(field => field.name === 'name' || field.name === 'uri');
//   const nonEditFields = fields.filter(field => field.name !== 'name' && field.name !== 'uri');

//   return (
//     <Dialog.Root open={isOpen} onOpenChange={onOpenChange}>
//       <Dialog.Content maxWidth="370px" className="w-[29%] p-[1.125rem] bg-[#111113] border-0 shadow-none">
//         <Flex justify="between" align="center">
//           <Text_16_600_FFFFFF className="p-0 m-0">{title}</Text_16_600_FFFFFF>
//           <Dialog.Close>
//             <Button className="m-0 p-0 bg-[transparent] h-[1.1rem]" size="1">
//               <Cross1Icon />
//             </Button>
//           </Dialog.Close>
//         </Flex>
//         <Dialog.Description className="text-xs text-[#44474D] pt-[.1rem]" mb="4">
//           <Text_12_300_44474D >{description}</Text_12_300_44474D>
//         </Dialog.Description>
//         {Object.keys(initialValues).length ? (
//           <>
//             <Flex gap="3" justify="between" className='flex-wrap'>
//               {nonEditFields.map((field) => (
//                 <label className="pb-1 w-[40%]" key={field.name}>
//                   <Text_12_400_787B83  mb="1">
//                     {field.label}
//                   </Text_12_400_787B83>
//                   <Text as="div" className="text-xs font-light text-[#6A6E76]" mb="1" weight="bold">
//                     {field.name}
//                   </Text>
//                 </label>
//               ))}
//             </Flex>
//             <Flex direction="column" gap="3" mt="4">
//               {editFields.map((field) => (
//                 <label className="pb-1" key={field.name}>
//                   <Text_12_400_787B83  mb="1">
//                     {field.label}
//                   </Text_12_400_787B83>
//                   <TextField.Root
//                     name={field.name}
//                     value={formData[field.name] || ''}
//                     onChange={(e) => handleChange(field.name, e.target.value)}
//                     placeholder={`Enter ${field.label.toLowerCase()}`}
//                     maxLength={100}
//                     className="h-[1.75rem] text-xs font-light rounded-md outline-[white] outline-1"
//                   />
//                 </label>
//               ))}
//             </Flex>
//             <Flex gap="3" mt="4" justify="center">
//               <Button size="1" className="h-[1.75rem] w-full text-xs font-normal" onClick={handleSubmit}>
//                 Update Model
//               </Button>
//             </Flex>
//           </>
//         ) : (
//           <>
//             <Flex direction="column" gap="3">
//               {textFields.map((field) => (
//                 <label className="pb-1" key={field.name}>
//                   <Text_12_400_787B83  mb="1">
//                     {field.label}<span className="text-[red]"> *</span>
//                   </Text_12_400_787B83>
//                   <TextField.Root
//                     name={field.name}
//                     value={formData[field.name] || ''}
//                     onChange={(e) => handleChange(field.name, e.target.value)}
//                     placeholder={`Enter ${field.label.toLowerCase()}`}
//                     maxLength={100}
//                     className="h-[1.75rem] text-xs font-light rounded-md outline-[white] outline-1"
//                   />
//                 </label>
//               ))}
//             </Flex>
//             <Flex direction="row" gap="3" mt="4">
//               {selectFields.map((field) => (
//                 <label className="pb-1" key={field.name}>
//                   <Text_12_400_787B83  mb="1">
//                     {field.label}<span className="text-[red]"> *</span>
//                   </Text_12_400_787B83>
//                   <Select.Root
//                     size="1"
//                     value={formData[field.name] || ''}
//                     onValueChange={(newValue) => handleChange(field.name, newValue)}
//                   >
//                     <Select.Trigger
//                       placeholder={`Select ${field.label.toLowerCase()}`}
//                       className="h-[1.75rem] text-xs font-light rounded-md outline-[white] outline-1"
//                     />
//                     <Select.Content>
//                       {field['options'].map((option, index) => (
//                         <Select.Item key={index} value={option}>
//                           {option}
//                         </Select.Item>
//                       ))}
//                     </Select.Content>
//                   </Select.Root>
//                 </label>
//               ))}
//             </Flex>
//             <Flex gap="3" mt="4" justify="center">
//               <Button size="1" className="h-[1.75rem] w-full text-xs font-normal" onClick={handleSubmit}>
//                 Add Model
//               </Button>
//             </Flex>
//           </>
//         )}
//       </Dialog.Content>
//     </Dialog.Root>
//   );
// };

// export default CommonModal;
