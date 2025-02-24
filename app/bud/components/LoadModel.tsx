import { Button, Popover } from "antd";
import React from "react";
import SearchHeaderInput from "./input/SearchHeaderInput";
import { ModelListCard } from "./ModelListCard";

function ModelLoaderComponent() {
  const [models, setModels] = React.useState([
    {
      id: "1",
      name: "Model Name",
      description: "Model Description",
      uri: "https://www.example.com",
      tags: ["tag1", "tag2"],
      provider: {
        icon: "https://www.example.com/icon.png",
      },
      is_present_in_model: false,
    },
    {
      id: "2",
      description: "Model Description",
      name: "Model Name",
      uri: "https://www.example.com",
      tags: ["tag1", "tag2"],
      provider: {
        icon: "https://www.example.com/icon.png",
      },
      is_present_in_model: false,
    },
  ]);
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
      <div className="w-full h-[320px] overflow-y-auto scrollbar-thin scrollbar-thumb-[#757575] scrollbar-track-[#1E1E1E] scrollbar-thumb-rounded-full scrollbar-track-rounded-full mt-[1rem]">
        {models.map((model) => (
          <ModelListCard
            data={{
              id: "1",
              name: "Model Name",
              description: "Model Description",
              uri: "https://www.example.com",
              tags: ["tag1", "tag2"],
              provider: {
                icon: "https://www.example.com/icon.png",
              },
              is_present_in_model: false,
            }}
          />
        ))}
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
