'use client';

import { useChat } from '@ai-sdk/react';
import { UIMessage } from '@ai-sdk/ui-utils';
import { MessageBox } from "react-chat-elements";
import IslandIcon from './IslandIcon';

function Message(props: UIMessage) {

  return <div className='text-[#FFFFFF] relative mb-[1.5rem]' style={{
    right: props.role === 'user' ? 0 : 0
  }}>
      {props.role === 'user' ?
        <MessageBox
          position='right'
          title=''
          type='text'
          text={props.content}
          // date={props.createdAt && new Date(props.createdAt) || new Date()}
          // status='received'
          replyButton={false}
          focus={false}
          forwarded={false}
          id={'122'}
          notch={false}
          removeButton={false}
          retracted={false}
          titleColor='#DDD'
          date={null as any}
          status={'' as any}
        />
        :
        <MessageBox
          position="left"
          title=""
          type="text"
          text={props.content}
          date={null as any}
          status={'' as any}
          focus
          id={'12'}
          forwarded={false}
          replyButton={false}
          notch={false}
          removeButton={false}
          retracted={false}
          titleColor='#FFF'
        />
      }
  </div>
}

function UserMessage(props: UIMessage) {

  return <div className=' whitespace-pre-wrap  p-[1rem]'>
    {props.content}
  </div>
}

function AIMessage(props: UIMessage) {
  return <div className='whitespace-pre-wrap  p-[1rem]'>
    {props.content}
  </div>
}

export default function Chat() {
  const {
    error,
    input,
    isLoading,
    handleInputChange,
    handleSubmit,
    messages,
    reload,
    stop,
  } = useChat({
    onFinish(message, { usage, finishReason }) {
      console.log('Usage', usage);
      console.log('FinishReason', finishReason);
    },
  });

  return (
    <main className='chat-container px-4'>
      <div className="flex flex-col w-full py-24 mx-auto stretch">
        {messages.map(m => (
          <Message {...m} key={m.id} />
        ))}
        {isLoading && (
          <div className="mt-4 text-gray-500">
            <div>Loading...</div>
            <button
              type="button"
              className="px-4 py-2 mt-4 text-blue-500 border border-blue-500 rounded-md"
              onClick={stop}
            >
              Stop
            </button>
          </div>
        )}

        {error && (
          <div className="mt-4">
            <div className="text-red-500">An error occurred.</div>
            <button
              type="button"
              className="px-4 py-2 mt-4 text-blue-500 border border-blue-500 rounded-md"
              onClick={() => reload()}
            >
              Retry
            </button>
          </div>
        )}

        <form onSubmit={handleSubmit} className='chat-message-form pt-2 fixed left-0 bottom-0 w-full flex items-center justify-center  mb-2 pb-2 border-[#e5e5e5] border-t-2'>
          <IslandIcon />
          <input
            className=" w-full max-w-5xl p-2 border border-gray-300 rounded shadow-xl placeholder-[#757575] placeholder-[.75rem] text-[.875rem] bg-transparent outline-none border-none text-[#757575]"
            value={input}
            placeholder="Say something..."
            onChange={handleInputChange}
            disabled={isLoading || error != null}
          />
        </form>
      </div>
    </main>
  );
}
