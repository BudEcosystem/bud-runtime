import * as Tooltip from "@radix-ui/react-tooltip";

interface ToolTipProps {
  triggerRenderItem: React.ReactNode;
  contentRenderItem: React.ReactNode;
  renderItemClassName?: React.ReactNode;
  arrowClasses?: React.ReactNode;
  align?: "start" | "center" | "end";
  side?: "top" | "right" | "bottom" | "left";
}

const ToolTip: React.FC<ToolTipProps> = ({
  triggerRenderItem,
  contentRenderItem,
  renderItemClassName,
  arrowClasses,
  align = "start",
  side = "top",
}) => {
  return (
    <Tooltip.Provider>
      <Tooltip.Root>
        <Tooltip.Trigger asChild className="cursor-pointer">
          {triggerRenderItem}
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            className={`data-[state=delayed-open]:data-[side=top]:animate-slideDownAndFade data-[state=delayed-open]:data-[side=right]:animate-slideLeftAndFade data-[state=delayed-open]:data-[side=left]:animate-slideRightAndFade data-[state=delayed-open]:data-[side=bottom]:animate-slideUpAndFade select-none rounded-[6px] px-[15px] py-[10px] text-[15px] leading-none shadow-[hsl(206_22%_7%_/_35%)_0px_10px_38px_-10px,_hsl(206_22%_7%_/_20%)_0px_10px_20px_-15px] will-change-[transform,opacity] ${renderItemClassName}`}
            sideOffset={5}
            align={align}
            side={side}
          >
            {contentRenderItem}
            <Tooltip.Arrow className={`${arrowClasses}`} />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );
};

export default ToolTip;
