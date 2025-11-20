"use client";
import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import React from "react";
import { Image, Popover } from "antd";
import {
  Text_10_400_B3B3B3,
  Text_10_400_D1B854,
  Text_12_400_EEEEEE,
  Text_16_400_EEEEEE,
} from "../../../../components/ui/text";
import { useRouter } from "next/router";
import SearchHeaderInput from "src/flows/components/SearchHeaderInput";
import HorizontalScrollFilter from "./components/filter";
import {
  useEvaluations,
  GetEvaluationsPayload,
  Evaluation,
} from "src/hooks/useEvaluations";
import { useLoader } from "src/context/appContext";

const EvaluationList = () => {
  const [selectedFilters, setSelectedFilters] = useState<string[]>([]);
  const [descriptionOverflows, setDescriptionOverflows] = useState<Map<string, boolean>>(new Map());
  const {
    getEvaluations,
    evaluationsList,
    evaluationsListTotal,
    getTraits,
    traitsList,
  } = useEvaluations();
  const { isLoading, showLoader, hideLoader } = useLoader();
  const router = useRouter();
  const [searchValue, setSearchValue] = useState("");
  const descriptionRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  const handleEvaluationClick = useCallback((evaluation: Evaluation) => {
    // Store the selected evaluation data in sessionStorage to pass to the detail page
    showLoader();
    sessionStorage.setItem('selectedEvaluation', JSON.stringify(evaluation));
    router.push(`/evaluations/${evaluation.id}`);
  }, [router]);

  useEffect(() => {
    const observers: ResizeObserver[] = [];

    descriptionRefs.current.forEach((el, id) => {
      const lineHeight = 16.8;
      const maxLines = 3;
      const maxHeight = lineHeight * maxLines;

      const observer = new ResizeObserver(() => {
        const isOverflowing = el.scrollHeight > maxHeight;

        setDescriptionOverflows(prev => {
          const map = new Map(prev);
          if (map.get(id) === isOverflowing) return prev; // No changes
          map.set(id, isOverflowing);
          return map;
        });
      });

      observer.observe(el);
      observers.push(observer);
    });

    return () => observers.forEach(o => o.disconnect());
  }, [evaluationsList]);   // depends on list

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

  // No longer need local filtering - use evaluationsList directly
  const filteredEvaluations = evaluationsList;

  useEffect(() => {
    const fetchEvaluations = async () => {
      // Find trait IDs for selected filter names
      const selectedTraitIds = selectedFilters.length > 0
        ? traitsList
            .filter(trait => selectedFilters.includes(trait.name))
            .map(trait => trait.id)
        : [];

      const payload: GetEvaluationsPayload = {
        page: 1,
        limit: 500,
        name: searchValue,
        trait_ids: selectedTraitIds.length > 0 ? selectedTraitIds : undefined,
      };
      await getEvaluations(payload);
    };
    fetchEvaluations();
  }, [searchValue, selectedFilters, traitsList, getEvaluations]);

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
            onClick={() => handleEvaluationClick(evaluation)}
          >
            <div className="flex flex-col justify-start">
              <div className=" flex justify-between items-start mb-[.5rem]">
                <Text_16_400_EEEEEE className="text-[16px]">
                  {evaluation.name}
                </Text_16_400_EEEEEE>
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
              <div className="mb-[2.15rem] relative">
                <div
                  ref={(el: HTMLDivElement | null) => {
                    // if (el) {
                    //   descriptionRefs.current.set(evaluation.id, el);
                    //   // Check if text overflows after rendering
                    //   setTimeout(() => {
                    //     const lineHeight = 16.8; // 140% of 12px
                    //     const maxLines = 3;
                    //     const maxHeight = lineHeight * maxLines;
                    //     if (el.scrollHeight > maxHeight) {
                    //       setDescriptionOverflows(prev => new Map(prev).set(evaluation.id, true));
                    //     }
                    //   }, 10);
                    // }
                    if (el) descriptionRefs.current.set(evaluation.id, el);
                  }}
                  className="text-xs font-normal text-[#EEEEEE] line-clamp-3 leading-[140%]"
                  style={{
                    display: '-webkit-box',
                    WebkitLineClamp: 3,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis'
                  }}
                >
                  {evaluation.description}
                </div>
                {descriptionOverflows.get(evaluation.id) && (
                  <Popover
                    content={
                      <div className="max-w-[400px] px-[.75rem] pb-[.75rem] ">
                        <div className="text-xs font-normal text-[#EEEEEE] leading-[140%]">
                          {evaluation.description}
                        </div>
                      </div>
                    }
                    title={
                      <span className="text-white font-medium px-[.75rem] !pt-[.55rem]">{evaluation.name}</span>
                    }
                    trigger="click"
                    placement="top"
                    color="#1F1F1F"
                    arrow={true}
                  >
                    <button
                      onClick={(e) => e.stopPropagation()}
                      className="text-[#D1B854] text-[10px] hover:text-[#E5CC60] transition-colors mt-1 underline inline-block"
                    >
                      See more
                    </button>
                  </Popover>
                )}
              </div>
            </div>

            {/* Footer */}
            <div className=" flex items-center justify-between mb-[.2rem]">
              <div className="flex items-center justify-start gap-[.6rem]">
                {evaluation.meta_links?.github && (
                  <a
                    href={evaluation.meta_links.github}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="flex justify-center h-[0.75rem] w-[0.75rem] hover:opacity-80 transition-opacity"
                  >
                    <Image
                      preview={false}
                      className=""
                      style={{ width: "auto", height: "0.75rem" }}
                      src="/images/evaluations/icons/cat.svg"
                      alt="GitHub"
                    />
                  </a>
                )}
                {evaluation.meta_links?.paper && (
                  <a
                    href={evaluation.meta_links.paper}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="flex justify-center h-[0.75rem] w-[0.75rem] hover:opacity-80 transition-opacity"
                  >
                    <Image
                      preview={false}
                      className=""
                      style={{ width: "auto", height: "0.75rem" }}
                      src="/images/evaluations/icons/lense.svg"
                      alt="Paper"
                    />
                  </a>
                )}
                {evaluation.meta_links?.website && (
                  <a
                    href={evaluation.meta_links.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="flex justify-center h-[.9rem] w-[.9rem] hover:opacity-80 transition-opacity"
                  >
                    <Image
                      preview={false}
                      className=""
                      style={{ width: "auto", height: ".9rem" }}
                      src="/images/icons/Globe.png"
                      alt="Website"
                    />
                  </a>
                )}
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
                <Text_10_400_B3B3B3 className="mr-2">
                  {evaluation.meta_links?.create_date
                    ? new Date(evaluation.meta_links.create_date).toLocaleDateString('en-US', {
                      month: '2-digit',
                      day: '2-digit',
                      year: 'numeric'
                    })
                    : ''}
                </Text_10_400_B3B3B3>
                {evaluation.meta_links?.creator?.avatar && (
                  <div className="creator">
                    <div className="flex justify-center h-[1.5rem] w-[1.5rem]">
                      <Image
                        preview={false}
                        className="rounded-full"
                        style={{
                          width: "1.5rem",
                          height: "auto",
                          objectFit: "cover"
                        }}
                        src={evaluation.meta_links.creator.avatar}
                        alt={evaluation.meta_links.creator.name || "Creator"}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default EvaluationList;
