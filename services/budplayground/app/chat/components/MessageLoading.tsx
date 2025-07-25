import { Image } from "antd";

export default function MessageLoading() {
  return (
    <div className="mt-4  flex flex-row  gap-[1rem]">
      <div>
        <Image
          preview={false}
          src="icons/budrect.svg"
          alt="bud"
          width={"1.25rem"}
          height={"1.25rem"}
        />
      </div>
      <div className="flex justify-start items-center gap-[.25rem]">
        <svg
          width="6"
          height="6"
          viewBox="0 0 6 6"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="animate-bounce delay-75"
        >
          <circle cx="3" cy="3" r="3" fill="#1F1F1F" />
        </svg>
        <svg
          width="6"
          height="6"
          viewBox="0 0 6 6"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="animate-bounce delay-150"
        >
          <circle cx="3" cy="3" r="3" fill="#1F1F1F" />
        </svg>

        <svg
          width="6"
          height="6"
          viewBox="0 0 6 6"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="animate-bounce delay-300"
        >
          <circle cx="3" cy="3" r="3" fill="#1F1F1F" />
        </svg>
      </div>
    </div>
  );
}
