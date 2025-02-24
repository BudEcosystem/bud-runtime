import { Button, Popover } from "antd";
import React from "react";
import SearchHeaderInput from "./input/SearchHeaderInput";

function ModelLoaderComponent() {
  const [searchValue, setSearchValue] = React.useState("");

  return (
    <div className="w-[520px] h-[400px] bg-[#1E1E1E]">
      <div className="">
        <SearchHeaderInput
          searchValue={searchValue}
          setSearchValue={setSearchValue}
          classNames="w-full h-[28px] bg-[#1E1E1E] border-[1px] border-[#3A3A3A] border-solid rounded-[4px] !text-[#FFF] pl-[1rem] !text-sm"
          expanded
          placeholder="Model names, Tags, Tasks, Parameter sizes"
        />
      </div>
    </div>
  );
}

function LoadModel() {
  const [open, setOpen] = React.useState(false);

  React.useEffect(() => {
    document.documentElement.scrollTop = document.documentElement.clientHeight;
    document.documentElement.scrollLeft = document.documentElement.clientWidth;
  }, []);

  return (
    <div>
      <Popover
      rootClassName="!mt-[-3.25rem]"
        arrow={false}
        content={<ModelLoaderComponent />}
        open={open}
      >
        <Button
          type="primary"
          className="text-[#FFF] w-[196px] h-[32px]"
          onClick={() => setOpen(!open)}
        >
          Load Model
        </Button>
      </Popover>
    </div>
  );
}

export default LoadModel;
