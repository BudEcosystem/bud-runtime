
import { useChatStore } from "@/app/store/chat";
import { Session } from "@/app/types/chat";
import { Image } from "antd";

function HistoryListItem({ data, chatId }: { data: Session, chatId: string }) {
    const { enableChat, disableChat } = useChatStore();
    return (
      <div
        onClick={() => {
            disableChat(chatId);
            enableChat(data.id);
          
        }}
        className={`flex flex-row items-center gap-[1rem] p-[.45rem] px-[.65rem] justify-between border-[1px] border-[#1F1F1F00] hover:border-[#1F1F1F] rounded-[8px] backdrop-blur-[10px] hover:bg-[#FFFFFF08] cursor-pointer ${chatId === data.id ? 'bg-[#FFFFFF08] border-[#1F1F1F]' : ''}`}
      >
        <div className="flex flex-row items-center gap-[.6rem] px-[.27rem]">
          <Image
            src="icons/list-item.svg"
            preview={false}
            alt="bud"
            width={".875rem"}
            height={".875rem"}
          />
          <span className="Lato-Regular text-[#EEE] text-[.875rem] font-[400]">
            {data.name}
          </span>
        </div>
  
        <span className="Open-Sans text-[#757575] text-[.625rem] font-[400] pr-[.15rem]">
          {data.total_tokens} tokens
        </span>
      </div>
    );
  }

export default function HistoryList({chatId}: {chatId: string}) {
    const { activeChatList } = useChatStore();
    return (
        <div className="flex flex-col w-full h-[41%] bg-[#101010] px-[.9rem] py-[.95rem] gap-y-[.6rem]">
          {activeChatList
            ?.slice()
            .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
            .map((item, index) => (
              <HistoryListItem key={index} data={item} chatId={chatId} />
            ))}
          {activeChatList?.length === 0 && (
            <div className="flex flex-row items-center justify-center w-full h-[2.5rem] bg-[#101010] rounded-[8px] border-[1px] border-[#1F1F1F] backdrop-blur-[10px]">
              <span className="Open-Sans text-[#757575] text-[.625rem] font-[400]">
                No chat history
              </span>
            </div>
          )}
        </div>
      );
}
