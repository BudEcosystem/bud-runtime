import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DeployModelSelect from "@/components/ui/bud/deploymentDrawer/DeployModelSelect";
import React, { useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { useModels } from "src/hooks/useModels";
import { useProjects } from "src/hooks/useProjects";
import { useDeployModel } from "src/stores/useDeployModel";
import ModelFilter from "@/components/ui/bud/deploymentDrawer/ModelFilter";
import { StepComponentsType } from "..";
import { usePerfomanceBenchmark } from "src/stores/usePerfomanceBenchmark";
import { useRoutes } from "src/hooks/useRoutes";
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import SearchHeaderInput from "../components/SearchHeaderInput";
import {
  Text_12_300_EEEEEE,
  Text_12_400_757575,
  Text_12_600_EEEEEE,
} from "@/components/ui/text";
import { Checkbox } from "antd";
import router from "next/router";
import { IEndPoint, useEndPoints } from "src/hooks/useEndPoint";
import EndpointCardWithCheckBox from "@/components/ui/CardWithCheckBox/EndpointCardWithCheckBox";

export default function SelectEndpointsForRoutes() {
  const { projectId } = router.query;
  const [order, setOrder] = useState<"-" | "">("-");
  const [orderBy, setOrderBy] = useState<string>("created_at");

  const [page, setPage] = React.useState(1);
  const [limit, setLimit] = React.useState(1000);

  const { endPoints, getEndPoints, endPointsCount } = useEndPoints();

  const [searchValue, setSearch] = React.useState("");
  const { selectedProjectId } = useProjects();
  const { openDrawerWithStep } = useDrawer();
  const [selectAllEndpoints, setSelectAllEndpoints] = useState<boolean>(false);
  const {
    setMultiSelectedEndpoints,
    multiSelectedEndpoints,
    setSelecteUnselectAllEndpoints,
    setEndpoints,
    endpoints,
    createRoute,
    setStepTwoData,
  } = useRoutes();

  const getData = async () => {
    await getEndPoints({
      id: projectId,
      page: page,
      limit: limit,
      name: searchValue,
      order_by: `${order}${orderBy}`,
    });
  };

  useEffect(() => {
    setStepTwoData();
  }, [multiSelectedEndpoints]);

  useEffect(() => {
    if (projectId) {
      getData();
    }
  }, [projectId, searchValue]);

  useEffect(() => {
    setEndpoints(endPoints);
  }, [endPoints]);

  const handleSelectAll = () => {
    setSelectAllEndpoints(!selectAllEndpoints);
    setSelecteUnselectAllEndpoints(selectAllEndpoints);
  };

  return (
    <BudForm
      data={{
        endpoints: [...multiSelectedEndpoints],
      }}
      disableNext={!multiSelectedEndpoints.length}
      onNext={async () => {
        createRoute();
        // openDrawerWithStep("Benchmark-Configuration");
      }}
      onBack={async () => {
        openDrawerWithStep("create-route-data");
      }}
      backText="Back"
      nextText="Next"
    >
      <BudWraperBox>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Se﻿lect Endpoints"
            description="Select the Endpoints and let’s start creating routes"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem]"
          />
          <DrawerCard>
            <div className="flex items-center justify-between gap-[0.625rem] pt-[.6rem] pb-[1.5rem]">
              <SearchHeaderInput
                placeholder="Endpoint names"
                searchValue={searchValue}
                expanded
                setSearchValue={setSearch}
                classNames="border border-[.5px] border-[#757575]"
              />
            </div>
            <div className="flex items-center justify-between pt-[.45rem]">
              <div className="flex items-center justify-start gap-[.2rem]">
                <Text_12_400_757575>
                  Endpoints Available&nbsp;
                </Text_12_400_757575>
                <Text_12_600_EEEEEE>{endPointsCount}</Text_12_600_EEEEEE>
              </div>
              {endPoints?.length > 0 && (
                <div className="flex items-center justify-start gap-[.7rem]">
                  <Text_12_600_EEEEEE>Select All</Text_12_600_EEEEEE>
                  <Checkbox
                    checked={selectAllEndpoints}
                    className="AntCheckbox text-[#757575] w-[0.875rem] h-[0.875rem] text-[0.875rem]"
                    onChange={handleSelectAll}
                  />
                </div>
              )}
            </div>
          </DrawerCard>
          <div className="">
            {endPoints?.length > 0 ? (
              <>
                {endPoints?.map((data: IEndPoint, index) => (
                  <EndpointCardWithCheckBox
                    key={index}
                    data={data}
                    handleClick={() => {
                      setMultiSelectedEndpoints(data);
                    }}
                    selected={multiSelectedEndpoints?.some(
                      (selected) => selected.id === data.id,
                    )}
                  />
                ))}
              </>
            ) : (
              <div className="flex justify-center items-center min-h-[4rem]">
                <Text_12_300_EEEEEE>No Endpoints available</Text_12_300_EEEEEE>
              </div>
            )}
          </div>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
