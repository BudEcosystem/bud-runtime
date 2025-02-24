import { Button } from "antd";
import React, { useEffect } from "react";
import SearchHeaderInput from "./input/SearchHeaderInput";
import { ModelListCard } from "./ModelListCard";
import BlurModal from "./modal/BlurModal";
import { useEndPoints } from "../hooks/useEndPoint";

function ModelLoaderComponent() {
  const { endPoints } = useEndPoints();
  const [searchValue, setSearchValue] = React.useState("");
  const [selected, setSelected] = React.useState("");

  return (
    <div>
      <div className="p-[1.25rem]">
        <SearchHeaderInput
          searchValue={searchValue}
          setSearchValue={setSearchValue}
          classNames="w-full h-[28px] bg-[#1E1E1E] border-[1px] border-[#3A3A3A] border-solid rounded-[4px] !text-[#FFF] pl-[1rem] !text-[.75rem] font-[400]"
          expanded
          placeholder="Model names, Tags, Tasks, Parameter sizes"
        />
      </div>
      <div className="w-full h-[320px] overflow-y-auto scrollbar-thin scrollbar-thumb-[#757575] scrollbar-track-[#1E1E1E] scrollbar-thumb-rounded-full scrollbar-track-rounded-full">
        <div className="flex justify-between items-center px-[1.25rem] py-[0.625rem]">
          <div className="text-[#757575] text-[0.75rem] font-[400]">
            Currently Loaded
            <span className="text-[#FFF] text-[0.75rem] font-[400] ml-[0.25rem]">
              {endPoints.length}
            </span>
          </div>
          <div className="text-[#757575] text-[0.625rem] font-[400]">
            Memory Consumption:
            <span className="text-[#FFF] text-[0.625rem] font-[400] ml-[0.25rem]">
              4.59/16 GB
            </span>
          </div>
        </div>
        {endPoints.map((model) => (
          <ModelListCard
            key={model.id}
            data={model}
            selected={selected === model.id}
            handleClick={() => {
              if (selected === model.id) {
                setSelected("");
              }
              setSelected(model.id);
            }}
          />
        ))}
      </div>
    </div>
  );
}
{
  /* <div>
    <Button type="primary" className="text-[#FFF] w-[196px] !h-[1.875rem]">
      <div className="text-[#FFF] text-[.75rem]"> Load Model</div>
    </Button>
  </div> */
}
function LoadModel() {
  const [open, setOpen] = React.useState(false);
  const { endPoints, getEndPoints } = useEndPoints();

  React.useEffect(() => {
    document.documentElement.scrollTop = document.documentElement.clientHeight;
    document.documentElement.scrollLeft = document.documentElement.clientWidth;
  }, []);

  useEffect(() => {
    console.log("getEndPoints");
    getEndPoints({ page: 1, limit: 10 });
  }, [open]);

  return (
    <div>
      <BlurModal
        width="520px"
        height="400px"
        open={open}
        onClose={() => setOpen(false)}
      >
        <ModelLoaderComponent />
      </BlurModal>
      <Button
        type="primary"
        className="text-[#FFF] w-[196px] h-[32px]"
        onClick={() => setOpen(!open)}
      >
        Load Model
      </Button>
    </div>
  );
}

export default LoadModel;
