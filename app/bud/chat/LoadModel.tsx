import { Button } from "antd";
import React, { useEffect } from "react";
import SearchHeaderInput from "../components/input/SearchHeaderInput";
import { ModelListCard } from "../components/ModelListCard";
import BlurModal from "../components/modal/BlurModal";
import { Endpoint, useEndPoints } from "../hooks/useEndPoint";

interface LoadModelProps {
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
  selected: Endpoint | null;
  setSelected: React.Dispatch<React.SetStateAction<Endpoint | null>>;
  openEdit: boolean;
  setOpenEdit: React.Dispatch<React.SetStateAction<boolean>>;
}

function LoadModel(props: LoadModelProps) {
  const { endPoints } = useEndPoints();
  const [searchValue, setSearchValue] = React.useState("");

  React.useEffect(() => {
    document.documentElement.scrollTop = document.documentElement.clientHeight;
    document.documentElement.scrollLeft = document.documentElement.clientWidth;
  }, []);

  return (
    <div>
      <BlurModal
        width="520px"
        height="400px"
        open={props.open}
        onClose={() => props.setOpen(false)}
      >
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
            {endPoints.map((endpoint) => (
              <ModelListCard
                key={endpoint.id}
                data={endpoint}
                selected={props.selected?.id === endpoint.id}
                handleClick={() => {
                  if (props.selected?.id === endpoint.id) {
                    return props.setSelected(null);
                  }
                  props.setSelected(endpoint);
                  props.setOpenEdit(true);
                  props.setOpen(false);
                }}
              />
            ))}
          </div>
        </div>
      </BlurModal>
      <Button
        type="primary"
        className="text-[#FFF] w-[196px] h-[32px]"
        onClick={() => props.setOpen(!props.open)}
      >
        Load Model
      </Button>
    </div>
  );
}

export default LoadModel;
