import { useNotifications, IMessage, useUnreadCount } from "@novu/notification-center";
import { differenceInHours, differenceInDays, format } from "date-fns";
import { ChevronDown } from "lucide-react";
import { useState, useEffect } from "react";
import { Text_12_400_A4A4A9, Text_14_600_EEEEEE, Text_10_400_757575, Text_24_600_EEEEEE, Text_10_400_EEEEEE, Text_12_400_757575 } from "../ui/text";
import { Flex, Image } from "antd";
import Tags from "src/flows/components/DrawerTags";
import { assetBaseUrl } from "../environment";
import IconRender from "src/flows/components/BudIconRender";

type NotificationPayload = {
    title: string;
    message: string;
    status?: string;
    time?: React.ReactNode;
    icon?: string;
}

export function Notification({ item, onClick }: { item?: NotificationPayload; onClick?: () => void }) {
    return (
        <div
            onClick={() => {}}
            className={`fileInput flex justify-between items-start px-[1.3rem] py-[1.25rem] bg-[#161616] border border-[#1F1F1F] rounded-[1rem] box-border width-300 transition-all duration-300 cursor-pointer height-88 `}>
            <div className="flex justify-start items-center  max-w-[65%]">
                <IconRender icon={item?.icon || ''} size={44} imageSize={24}/>
                <div className="pt-[.3rem] max-w-[94%] ml-[.75rem]">
                    <Text_12_400_A4A4A9 className={`tracking-[-.01rem] max-w-[80%] transition-all duration-300 truncate`}>
                        {item?.title}
                    </Text_12_400_A4A4A9>
                    <div className="flex justify-between items-center ">
                        <Text_14_600_EEEEEE className={`tracking-[-.01rem] transition-all duration-300 truncate `}>
                            {
                                item?.message
                            }</Text_14_600_EEEEEE>
                        {item?.status === 'COMPLETED' && <div className="w-[1.5rem] h-[1.5rem] ml-[.5rem]" >
                            <Image
                                preview={false}
                                src="/images/drawer/tickCut.png"
                                alt="info"
                                width={'1.5rem'}
                                height={'1.5rem'}
                            />
                        </div>}
                    </div>
                </div>
            </div>
            <div className="flex flex-col items-end justify-between h-[2.75rem]">
                <Text_10_400_757575 className="whitespace-nowrap">
                    {/* {formatDistanceToNow(new Date(item?.createdAt), { addSuffix: true })} */}
                    {/* {format(new Date(item?.createdAt), 'hh:mm')} */}
                    {item?.time}
                </Text_10_400_757575>
                {/* {item?.status && item?.status !== 'COMPLETED' && <Tags name={item?.status} color="#EC7575" />} */}
            </div>
        </div>
    );
}


export type NotificationItem = {
    title: string;
    message: string;
    time: React.ReactNode;
    status: string;
    icon: string;
}

export function NotificationsWidget({
    notifications,
    loadNotifications,
    loading
}: {
    notifications?: NotificationItem[];
    loadNotifications: () => void;
    loading: boolean;
}) {
    const { markAllNotificationsAsRead } = useNotifications();

    const [isClosed, setIsClosed] = useState(true); // State to track the class
    const toggleList = () => {
        setIsClosed(!isClosed); // Toggle between open and closed
    };

    const gridRowCount = Math.ceil((notifications?.length || 0) / 2);

    console.log('notifications', Math.ceil(gridRowCount));

    return <>

        <div className={`item rounded-[16px] py-[1.25rem] border border-[#1F1F1F] rounded-[16px]   width-full box-border ${isClosed ? 'height-211 ' : 'h-full '}  item max-h-[90vh] overflow-y-hidden`}
            style={{
                gridRow: `1 / span ${isClosed ? 1 : gridRowCount > 3 ? 3 : gridRowCount}`
            }}
        >
            <div className="flex justify-between items-center  px-[1.5rem]">
                <Text_24_600_EEEEEE className="tracking-[-.015rem]">Notifications</Text_24_600_EEEEEE>
                <div className="flex justify-end items-center ">
                    {notifications && notifications?.length > 1 && <div className="w-[1.25rem] h-[1.25rem] rounded-full flex justify-center items-center mr-[.6rem] bg-[#161616] cursor-pointer"
                        onClick={toggleList}
                    >
                        <ChevronDown
                            className={`text-[#EEEEEE] w-[1.1rem] transition-transform duration-300 ${isClosed ? '' : 'rotate-180'}`}
                        />
                    </div>}
                    {notifications && notifications?.length > 0 &&
                        <div className="px-[.4rem] py-[.32rem] rounded-[43px] bg-[#161616] cursor-pointer" onClick={async () => {
                            await markAllNotificationsAsRead();
                            loadNotifications();
                            setIsClosed(true);
                        }}>
                            <Text_10_400_EEEEEE>Clear all</Text_10_400_EEEEEE>
                        </div>}
                </div>
            </div>
            {loading && <div className="flex justify-center items-center h-full">
                <Text_12_400_757575>Loading...</Text_12_400_757575>
            </div>}
            {
                notifications?.length === 0 || !notifications ? <div className="flex justify-center items-center h-full">
                    <Text_12_400_757575 className="py-[1rem]">No Notifications are available</Text_12_400_757575></div> :
                    notifications?.length > 0 &&
                    <div className={`notificationList mt-[1.3rem] max-h-[93%] flex flex-col gap-[.7rem] ${isClosed && notifications?.length > 1 ? 'closed' : 'showing'} ${notifications?.length == 2 && 'twoData'}  px-[1.5rem] transition-all duration-300`}>
                        {
                            [...notifications]
                                ?.splice(0, isClosed ? 1 : notifications.length)
                                ?.map((item, index: number) => (
                                    <Notification key={index} item={item}
                                        onClick={() => {
                                            if (isClosed) {
                                                toggleList();
                                            }
                                        }}
                                    />
                                ))}

                    </div>
            }
        </div>
        {/* {!isClosed && notifications.length > 2 && <div className="flex justify-center items-center mt-[.6rem]"></div>} */}
    </>
}
