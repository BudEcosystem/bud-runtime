import * as React from "react";
import { Icon } from "@iconify/react";
import classNames from "classnames";
import { useState } from "react";

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
  checkedChange?: boolean;
  onCheckedChange?: (checked: boolean) => void;
  onClick?: () => void;
  id?: string;
  [key: string]: any;
}

const CheckBoxInput: React.FC<CheckBoxInputProps> = ({
  className,
  indicatorClassName,
  defaultCheck = false,
  checkedChange,
  onClick,
  id,
  ...props
}) => {
  const [isChecked, setIsChecked] = useState(defaultCheck);

  React.useEffect(() => {
    if (checkedChange !== undefined) {
      setIsChecked(checkedChange);
    }
  }, [checkedChange]);

  const handleCheckedChange = (checked: boolean) => {
    setIsChecked(checked);
  };

  return (
    <div className="flex items-center">
      <label className="relative">
        <input
          type="checkbox"
          id={id}
          className="sr-only"
          checked={isChecked}
          onChange={(e) => handleCheckedChange(e.target.checked)}
          onClick={onClick}
          {...props}
        />
        <div
          className={classNames(
            `w-[0.875rem] h-[0.875rem] border border-[#757575] rounded-[0.25rem] hover:border-[#965CDE] hover:shadow-[0_0_1.9px_1px_rgba(150,92,222,0.6)] cursor-pointer flex items-center justify-center`,
            {
              "border-[#965CDE] !bg-[#965CDE]": isChecked,
              [className || ""]: className,
            }
          )}
        >
          {isChecked && (
            <Icon
              icon="material-symbols:check"
              className={classNames("text-[black] h-[100%] w-[100%]", {
                [indicatorClassName || ""]: indicatorClassName,
              })}
            />
          )}
        </div>
      </label>
    </div>
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
}) => {
  const [value, setValue] = useState(defaultValue || [0]);

  return (
    <div
      className={classNames(
        `budSlider relative block flex items-center select-none touch-none w-full border border-[#212225] !h-[0.725rem] max-h-[0.725rem] py-[.8rem] px-[.5rem] rounded-md ${className}`
      )}
    >
      <div className={`bg-[#212225] relative grow rounded-full h-[3px] ${classTrack}`}>
        <div
          className={`absolute bg-[#965CDE] rounded-full h-full ${classRange}`}
          style={{ width: `${(value[0] / (props.max || 100)) * 100}%` }}
        />
      </div>
      <input
        type="range"
        className={`absolute w-full h-full opacity-0 cursor-pointer ${classThumb}`}
        aria-label="Volume"
        value={value[0]}
        onChange={(e) => {
          const newValue = [Number(e.target.value)];
          setValue(newValue);
          props.onValueChange?.(newValue);
        }}
        {...props}
      />
      <div
        className={`block w-[8px] h-[8px] bg-white rounded-full cursor-pointer absolute ${classThumb}`}
        style={{ left: `${(value[0] / (props.max || 100)) * 100}%`, transform: 'translateX(-50%)' }}
      />
    </div>
  );
};

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
}) => {
  const [checked, setChecked] = useState(defaultCheck || false);

  return (
    <label className={`inline-flex items-center ${className}`}>
      <input
        type="checkbox"
        className="sr-only"
        checked={checked}
        disabled={disabled}
        onChange={(e) => {
          setChecked(e.target.checked);
          props.onCheckedChange?.(e.target.checked);
        }}
        {...props}
      />
      <div
        className={classNames(
          `w-[1.4375rem] h-[0.725rem] bg-[#212225] rounded-full relative shadow-none border border-[#181925] cursor-pointer transition-colors duration-200`,
          {
            'bg-[#965CDE]': checked,
            'opacity-50 cursor-not-allowed': disabled,
          },
          classNameRoot
        )}
      >
        <div
          className={classNames(
            `block w-[0.55rem] h-[0.55rem] bg-white rounded-full transition-transform duration-100 absolute top-1/2 transform -translate-y-1/2`,
            {
              'translate-x-0.5': !checked,
              'translate-x-[0.75rem]': checked,
            },
            classNameThump
          )}
        />
      </div>
    </label>
  );
};

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
  <div className="relative w-full max-w-[350px]">
    <input
      maxLength={100}
      className={`w-full text-[0.740625rem] font-light text-[#44474D] h-[1.75rem] bg-[#0f0f0f] outline-[.5px] outline-[white] rounded-md border border-[#212225] shadow-none bg-transparent leading-[100%] px-3 hover:border-[#63656c] focus:border-[#965CDE] focus:outline-none ${className}`}
      {...props}
    />
    {textFieldSlot && textFieldSlot}
  </div>
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
  <textarea
    style={{ fontSize: "0.740625rem !important" }}
    className={`w-full max-w-[350px] min-h-[50px] text-[0.740625rem] font-light text-[#44474D] bg-[#0f0f0f] outline-[.5px] outline-[white] rounded-md border border-[#212225] shadow-none bg-transparent placeholder:text-xs placeholder:font-light hover:border-[#63656c] focus:border-[#965CDE] focus:outline-none resize-vertical px-3 py-2 ${className}`}
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

  const handleSearch = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event?.target?.value?.toLowerCase();
    setSearchTerm(value);
    setFilteredItems(
      selectItems.filter((item: any) =>
        (renderItem ? renderItem(item) : item.label || item)?.toLowerCase()?.includes(value)
      )
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
  const [isOpen, setIsOpen] = useState(false);

  const handleToggle = () => {
    if (selectItems?.length === 0) return;
    const newState = !isOpen;
    setIsOpen(newState);
    setState(newState ? "open" : "closed");
    if (!newState) {
      setSearchTerm("");
      setFilteredItems(selectItems);
    }
  };

  const handleSelect = (item: any) => {
    onValueChange(item);
    setIsOpen(false);
    setState("closed");
  };

  return (
    <div className="relative w-full max-w-[350px]">
      <div
        onClick={handleToggle}
        className={classNames(
          `w-full h-[1.75rem] px-[.3rem] outline-[.5px] outline-[white] rounded-md border border-[#212225] bg-transparent text-[#FFFFFF] text-nowrap text-xs font-light cursor-pointer hover:border-[#63656c] flex justify-between items-center`,
          {
            "border-[white]": state === "open",
            "opacity-50 cursor-not-allowed": selectItems?.length === 0,
          },
          className
        )}
      >
        <div className={`w-[100%] truncate text-left ${valueClassName}`}>
          <span className={`text-white text-left text-nowrap text-[.75rem] font-light leading-[100%] truncate block ${valueClassName} ${!value && !defaultValue ? 'text-[#6A6E76]' : ''}`}>
            {value ? value : defaultValue ? defaultValue : placeholder}
          </span>
        </div>
        <Icon
          icon="material-symbols:arrow-drop-down"
          className="text-[1.1rem] text-[#ffffff] ml-2"
        />
      </div>

      {isOpen && (
        <div className="absolute top-full left-0 w-full mt-1 bg-[#111113] text-xs text-[#FFFFFF] border border-[#212225] rounded-md p-[.5rem] box-border z-50 max-h-[200px] overflow-y-auto">
          {isSearchVisible && (
            <input
              placeholder="Search"
              className="h-7 w-full placeholder:text-xs mb-2 text-xs text-[#EEEEEE] hover:bg-white hover:bg-opacity-[3%] placeholder:text-[#808080] font-light outline-none bg-transparent border border-[#212225] rounded-[5px] py-1 px-2.5"
              type="text"
              value={searchTerm}
              onChange={handleSearch}
              onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) =>
                e.stopPropagation()
              }
            />
          )}

          {filteredItems &&
            filteredItems.map((item: any, index: number) => (
              <div
                key={index}
                className="h-[1.75rem] py-[.5rem] px-[.8rem] w-full hover:bg-[#18191B] rounded-md cursor-pointer border-none shadow-none outline-0 leading-[100%]"
                onClick={() => handleSelect(item)}
              >
                <span className="border-none shadow-none text-xs text-left text-[#FFFFFF] font-normal leading-[100%] truncate">
                  {renderItem ? renderItem(item) : item.label || item}
                </span>
              </div>
            ))
          }
        </div>
      )}
    </div>
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

  const handleSearch = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event?.target?.value?.toLowerCase();
    setSearchTerm(value);
    setFilteredItems(
      selectItems.filter((item: any) =>
        (renderItem ? renderItem(item) : item.label || item)
          ?.toLowerCase()
          ?.includes(value)
      )
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
  const [isOpen, setIsOpen] = useState(false);

  const handleToggle = () => {
    if (selectItems.length === 0) return;
    const newState = !isOpen;
    setIsOpen(newState);
    setState(newState ? "open" : "closed");
    if (!newState) {
      setSearchTerm("");
      setFilteredItems(selectItems);
    }
  };

  const handleSelect = (item: any) => {
    onValueChange(item);
    setIsOpen(false);
    setState("closed");
  };

  return (
    <div className="relative w-full max-w-[350px]">
      <div
        onClick={handleToggle}
        className={classNames(
          `w-full h-[1.75rem] px-[.3rem] outline-[.5px] outline-[white] rounded-md border border-[#212225] bg-transparent text-[white] text-nowrap text-xs font-light cursor-pointer hover:border-[#63656c] flex justify-between items-center`,
          {
            "border-[white]": state === "open",
            "opacity-50 cursor-not-allowed": selectItems.length === 0,
          },
          className
        )}
      >
        <div className="w-[100%] truncate text-left">
          <span className={`text-white text-left text-nowrap text-[.75rem] font-light leading-[100%] truncate block ${!value && !defaultValue ? 'text-[#6A6E76]' : ''}`}>
            {value ? value : defaultValue ? defaultValue : placeholder}
          </span>
        </div>
        <Icon
          icon="material-symbols:arrow-drop-down"
          className="text-[1.1rem] text-[#ffffff] ml-2"
        />
      </div>

      {isOpen && (
        <div className="absolute top-full left-0 w-full mt-1 bg-[#111113] text-xs text-[#FFFFFF] border border-[#212225] rounded-md p-[.5rem] box-border z-50 max-h-[200px] overflow-y-auto">
          {isSearchVisible && (
            <input
              placeholder="Search"
              className="h-7 w-full placeholder:text-xs mb-2 text-xs text-[#EEEEEE] hover:bg-white hover:bg-opacity-[3%] placeholder:text-[#808080] font-light outline-none bg-transparent border border-[#212225] rounded-[5px] py-1 px-2.5"
              type="text"
              value={searchTerm}
              onChange={handleSearch}
              onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) =>
                e.stopPropagation()
              }
            />
          )}

          {filteredItems &&
            filteredItems.map((item: any, index: number) => (
              <div
                key={index}
                className="h-[1.75rem] py-[.5rem] px-[.8rem] w-full hover:bg-[#18191B] rounded-md cursor-pointer border-none shadow-none outline-0 leading-[100%]"
                onClick={() => handleSelect(item)}
              >
                <span className="border-none shadow-none text-xs text-left text-[#FFFFFF] font-normal leading-[100%] truncate">
                  {renderItem ? renderItem(item) : item.label || item}
                </span>
              </div>
            ))
          }
        </div>
      )}
    </div>
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
    e: React.MouseEvent<HTMLButtonElement>
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
          <button
            onClick={handleClick}
            className="flex rounded-md bg-transparent border border-dashed border-[#44474D] text-left py-[.8rem] px-4 items-center justify-start hover:border-[#965CDE] transition-colors"
          >
            <Icon icon="material-symbols:note-add-outline" className="text-[#44474D] mr-2" />
            <Text_12_300_44474D className="leading-full">
              Choose Files
            </Text_12_300_44474D>
          </button>
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
                className="remove-file-btn ml-2 hover:text-red-400 transition-colors"
              >
                <Icon icon="material-symbols:close" className="text-red-500" />
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
