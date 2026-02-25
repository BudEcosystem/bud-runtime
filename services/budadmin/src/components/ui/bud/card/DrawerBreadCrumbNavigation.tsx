import { Breadcrumb } from "antd";
import React from "react";
import { Text_12_400_5B6168, Text_12_400_787B83 } from "../../text";
import { ShrinkOutlined } from "@ant-design/icons";
import { useDrawer } from "src/hooks/useDrawer";
import { Cross1Icon } from "@radix-ui/react-icons";
import Link from "next/link";
import { useWorkflow } from "src/stores/useWorkflow";

export function CustomBreadcrumb({
  data,
  urls,
}: {
  data: string[];
  urls?: string[];
}) {
  return (
    // <Breadcrumb
    //   separator={<Text_12_400_5B6168 className="mx-2">/</Text_12_400_5B6168>}
    //   items={data?.map((item, index) => ({
    //     href: "#",
    //     title:
    //       index === 0 ? (
    //         <Link href={urls ? urls[index] : "#"}>
    //           <Text_12_400_5B6168 className="inline-flex items-center ">
    //             {item}
    //           </Text_12_400_5B6168>
    //         </Link>
    //       ) : (
    //         urls ? urls[index] != '' ? (
    //           <Link href={urls ? urls[index] : "#"}>
    //             <Text_12_400_787B83 className="text-white">
    //               {item}
    //             </Text_12_400_787B83>
    //           </Link>
    //         ) : (
    //           <Text_12_400_787B83 className="text-white cursor-normal">
    //             {item}
    //           </Text_12_400_787B83>
    //         ) : null
    //       )
    //   })) || []
    //   }
    // />
    <Breadcrumb
      separator={<Text_12_400_5B6168 className="mx-2">/</Text_12_400_5B6168>}
      items={
        data?.map((item, index) => {
          const isLast = index === data.length - 1;
          const hasUrl = urls?.[index];

          return {
            title:
              !isLast && hasUrl ? (
                <Link href={hasUrl}>
                  <Text_12_400_787B83
                    className='hover:cursor-pointer hover:text-[#EEEEEE] capitalize'
                  >
                    {item}
                  </Text_12_400_787B83>
                </Link>
              ) : (
                <Text_12_400_787B83
                  className='cursor-default text-[#EEEEEE] capitalize'
                >
                  {item}
                </Text_12_400_787B83>
              ),
          };
        }) || []
      }
    />
  )
}

export function DeawerCustomBreadcrumb({
  data,
  urls,
}: {
  data: string[];
  urls?: string[];
}) {
  return <Breadcrumb
    separator={<Text_12_400_5B6168 className="mx-2">/</Text_12_400_5B6168>}
    items={data?.map((item, index) => ({
      title:
        index === 0 ?
          (
            <Link href={urls ? urls[index] : "#"}>
              <Text_12_400_5B6168 className="inline-flex items-center ">
                {item}
              </Text_12_400_5B6168>
            </Link>
          ) :
          <Link href={urls ? urls[index] : "#"}>
            <Text_12_400_787B83 className="text-white">
              {item}
            </Text_12_400_787B83>
          </Link>
    })) || []
    }
  />
}

// Deploy Model
function DrawerBreadCrumbNavigation({
  items: data,
  showMinimizeButton,
}: {
  items: string[];
  showMinimizeButton?: boolean;
}) {
  const { closeDrawer, setCancelAlert, step, minimizeProcess } = useDrawer();
  return (
    <div
      className=" ant-header-breadcrumb"
    >
      <div className="flex items-center gap-2 mr-4">
        <button onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          if (step.confirmClose) {
            return setCancelAlert(true);
          }
          closeDrawer();

        }}>
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg" className="hover:text-[#FFFFFF] mr-.5">
            <path fillRule="evenodd" clipRule="evenodd" d="M13.8103 5.09188C14.0601 4.8421 14.0601 4.43712 13.8103 4.18734C13.5606 3.93755 13.1556 3.93755 12.9058 4.18734L8.99884 8.0943L5.09188 4.18734C4.8421 3.93755 4.43712 3.93755 4.18734 4.18734C3.93755 4.43712 3.93755 4.8421 4.18734 5.09188L8.0943 8.99884L4.18734 12.9058C3.93755 13.1556 3.93755 13.5606 4.18734 13.8103C4.43712 14.0601 4.8421 14.0601 5.09188 13.8103L8.99884 9.90338L12.9058 13.8103C13.1556 14.0601 13.5606 14.0601 13.8103 13.8103C14.0601 13.5606 14.0601 13.1556 13.8103 12.9058L9.90338 8.99884L13.8103 5.09188Z" fill="#B3B3B3" />
          </svg>
        </button>
        {showMinimizeButton && (
          <button onClick={() => {
          if (!step?.id) {
            return closeDrawer();
          };
          document.getElementById("bud-drawer")?.classList.toggle("hide-drawer");
          minimizeProcess({
            ...step,
          })
        }}>
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg" className="hover:text-[#FFFFFF] ">
            <path fillRule="evenodd" clipRule="evenodd" d="M15.5654 14.748C16.104 15.2866 15.2856 16.1044 14.747 15.5665L11.1293 11.9481V13.9429C11.1293 14.7044 9.972 14.7044 9.972 13.9429L9.9727 10.5517C9.9727 10.2325 10.2322 9.97302 10.5514 9.97302H13.9433C14.7048 9.97302 14.7048 11.1304 13.9433 11.1304L11.9478 11.1297L15.5654 14.748ZM7.6123 4.79945C7.6123 4.03796 8.76965 4.03796 8.76965 4.79945V8.19137C8.76965 8.51058 8.5102 8.77003 8.19099 8.77003L4.79907 8.76933C4.03758 8.76933 4.03758 7.61198 4.79907 7.61198H6.79383L3.17619 3.99434C2.63759 3.45574 3.45603 2.638 3.99463 3.1759L7.61227 6.79354L7.6123 4.79945Z" fill="#B3B3B3" />
          </svg>
        </button>
        )}
      </div>
      <DeawerCustomBreadcrumb data={data} />
    </div>
  );
}

export default DrawerBreadCrumbNavigation;
