"use client";
import { useState, useEffect, useMemo, useCallback } from "react";
import React from "react";
import { Image } from "antd";
import {
  Text_10_400_B3B3B3,
  Text_10_400_D1B854,
  Text_10_400_EEEEEE,
  Text_14_400_EEEEEE,
} from "../../../../components/ui/text";
import { PrimaryButton } from "@/components/ui/bud/form/Buttons";
import { useRouter } from "next/router";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import HorizontalScrollFilter from "./components/filter";
import {
  useEvaluations,
  GetEvaluationsPayload,
  Evaluation,
} from "src/hooks/useEvaluations";

const EvaluationList = () => {
  const [selectedFilters, setSelectedFilters] = useState<string[]>([]);
  const {
    getEvaluations,
    evaluationsList,
    evaluationsListTotal,
    getTraits,
    traitsList,
  } = useEvaluations();
  const router = useRouter();
  const [searchValue, setSearchValue] = useState("");

  const handleFilterToggle = useCallback((filterName: string) => {
    setSelectedFilters((prev) => {
      if (prev.includes(filterName)) {
        // Remove filter if already selected
        return prev.filter((f) => f !== filterName);
      } else {
        // Add filter if not selected
        return [...prev, filterName];
      }
    });
  }, []);

  const getTypeIcon = useCallback((type: string) => {
    const iconMap: Record<string, string> = {
      text: "/images/evaluations/icons/text.svg",
      image: "/images/evaluations/icons/image.svg",
      video: "/images/evaluations/icons/video.svg",
      actions: "/images/evaluations/icons/actions.svg",
      embeddings: "/images/evaluations/icons/embeddings.svg",
    };

    const iconSrc = iconMap[type.toLocaleLowerCase()];
    if (!iconSrc) return null;

    return (
      <div className="flex justify-center h-[0.75rem] w-[0.75rem]">
        <img
          className="w-auto h-[0.75rem]"
          src={iconSrc}
          alt={type}
          loading="lazy"
        />
      </div>
    );
  }, []);

  const filteredEvaluations = useMemo(() => {
    const searchLower = searchValue.toLowerCase();
    return evaluationsList?.filter((evaluation) => {
      const matchesSearch =
        evaluation.name.toLowerCase().includes(searchLower) ||
        evaluation.description.toLowerCase().includes(searchLower);
      const matchesFilter =
        selectedFilters.length === 0 ||
        evaluation.traits?.some((trait) =>
          selectedFilters.includes(trait.name),
        );
      return matchesSearch && matchesFilter;
    });
  }, [searchValue, selectedFilters, evaluationsList]);

  useEffect(() => {
    const fetchEvaluations = async () => {
      const payload: GetEvaluationsPayload = {
        page: 1,
        limit: 500,
        name: searchValue,
      };
      await getEvaluations(payload);
    };
    fetchEvaluations();
  }, [searchValue, getEvaluations]);

  useEffect(() => {
    getTraits();
  }, []);

  useEffect(() => {
    // console.log('traitsList', traitsList)
  }, [traitsList]);

  return (
    <div className="w-full">
      <div className="pt-[3.34rem] flex flex-col items-center">
        {/* <div className="pt-[3.34rem] mx-auto projectDetailsDiv "> */}
        <div className="flex justify-center h-[3.1rem] w-[3.1rem] ">
          <Image
            preview={false}
            className=""
            style={{ width: "auto", height: "3.1rem" }}
            src="/budicon.png"
            alt="Logo"
          />
        </div>
        <div className="flex items-center gap-4 pt-[2rem] relative w-[70.4%]">
          <SearchHeaderInput
            searchValue={searchValue}
            setSearchValue={setSearchValue}
            placeholder="Type in anything you would like to evaluate: finance, healthcare, hindi, problem solving et"
            expanded={true}
            classNames="flex-1 border-[.5px] border-[#757575]"
          />
          <div className="flex items-center gap-6 text-[#757575] text-sm absolute right-[1rem]">
            <Text_10_400_B3B3B3>
              {filteredEvaluations?.length || 0}/{evaluationsListTotal}
            </Text_10_400_B3B3B3>
          </div>
        </div>

        {/* Filter Pills */}
        <div className="mt-[2rem] mb-[.4rem] w-[90%] ">
          {traitsList.length > 0 && (
            <HorizontalScrollFilter
              filters={traitsList.map((trait) => trait.name)}
              selectedFilters={selectedFilters}
              onFilterClick={handleFilterToggle}
            />
          )}
        </div>
      </div>

      {/* Evaluation Cards Grid */}
      <div className="mt-[2.8rem] flex flex-wrap justify-between gap-[.8rem] max-w-full pb-[1rem]">
        {filteredEvaluations.map((evaluation) => (
          <div
            key={evaluation.id}
            className="w-[49.2%] bg-[#101010] border border-[#1F1F1F] rounded-[0.4rem] px-[1.5rem] py-[1.1rem] hover:shadow-[1px_1px_6px_-1px_#2e3036] transition-all cursor-pointer flex flex-col justify-between"
            onClick={() => router.push(`/evaluations/${evaluation.id}`)}
          >
            <div className="flex flex-col justify-start">
              <div className=" flex justify-between items-start mb-[.5rem]">
                <Text_14_400_EEEEEE className="text-[16px]">
                  {evaluation.name}
                </Text_14_400_EEEEEE>
              </div>

              {/* Combined Type and Trait Tags */}
              <div className="flex flex-wrap gap-2 mb-[.5rem]">
                {/* Modality Tags */}
                {evaluation.modalities?.map((type) => (
                  <div
                    key={type}
                    className="flex items-center gap-[.1rem] px-[.5rem] py-[.2rem] bg-[#1F1F1F] rounded-[0.375rem]"
                  >
                    {getTypeIcon(type)}
                    <Text_10_400_D1B854 className="capitalize">
                      {type}
                    </Text_10_400_D1B854>
                  </div>
                ))}

                {/* Trait Tags */}
                {evaluation.traits?.map((trait) => (
                  <div
                    key={trait.id || trait.name}
                    className="flex items-center gap-[.1rem] px-[.5rem] py-[.2rem] bg-[#1F1F1F] rounded-[0.375rem]"
                  >
                    <Text_10_400_D1B854 className="capitalize">
                      {trait.name}
                    </Text_10_400_D1B854>
                  </div>
                ))}
              </div>

              {/* Description */}
              <Text_10_400_EEEEEE className="line-clamp-2 mb-[2.15rem] leading-[140%]">
                {evaluation.description}
              </Text_10_400_EEEEEE>
            </div>

            {/* Footer */}
            <div className=" flex items-center justify-between mb-[.2rem]">
              <div className="flex items-center justify-start gap-[.6rem]">
                <div className="flex justify-center h-[0.75rem] w-[0.75rem]">
                  <Image
                    preview={false}
                    className=""
                    style={{ width: "auto", height: "0.75rem" }}
                    src="/images/evaluations/icons/cat.svg"
                    alt="Logo"
                  />
                </div>
                <div className="flex justify-center h-[0.75rem] w-[0.75rem]">
                  <Image
                    preview={false}
                    className=""
                    style={{ width: "auto", height: "0.75rem" }}
                    src="/images/evaluations/icons/lense.svg"
                    alt="Logo"
                  />
                </div>
              </div>
              <div className="flex items-center gap-1 justify-end">
                <div className="flex justify-center h-[0.75rem] w-[0.75rem]">
                  <Image
                    preview={false}
                    className=""
                    style={{ width: "auto", height: "0.75rem" }}
                    src="/images/evaluations/icons/time.svg"
                    alt="Logo"
                  />
                </div>
                {/* <Text_10_400_B3B3B3>{evaluation.timestamp}</Text_10_400_B3B3B3> */}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default EvaluationList;
