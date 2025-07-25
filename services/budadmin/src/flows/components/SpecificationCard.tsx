import { Text_14_600_EEEEEE } from "@/components/ui/text";
import { getSpecValueWidthOddEven } from "@/lib/utils";
import {
  SpecificationTableItem,
  SpecificationTableItemProps,
} from "./SpecificationTableItem";
import { use, useEffect } from "react";

export const SpecificationCard = ({
  title,
  specifications,
}: {
  title: string;
  specifications: SpecificationTableItemProps[];
}) => {

  return (
    <div className="p-[1.35rem] pt-0 flex justify-between items-center flex-wrap gap-y-[1.5rem]">
      {title && (
        <div className="w-full">
          <Text_14_600_EEEEEE>{title}</Text_14_600_EEEEEE>
        </div>
      )}
      <div className="flex flex-col justify-between items-start gap-y-[1.5rem] w-full">
        {specifications.map((item, index) => (
          <SpecificationTableItem
            key={index}
            item={item}
            valueWidth={220}
            // valueWidth={getSpecValueWidthOddEven(specifications, index)}
            // edits made to fix ui issue
          />
        ))}
      </div>
    </div>
  );
};
