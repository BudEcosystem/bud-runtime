import React, { useEffect, useState } from "react";
import LabelInput from "./bud/components/input/LabelInput";
import { useRouter } from "next/navigation";

function APIKey() {
  const [apiKey, setApiKey] = useState<string>("");
  const router = useRouter();

  const handleAdd = () => {
    router.replace(`?api_key=${apiKey}`);
  };

  return (
    <div className="w-full max-w-[20rem]">
      <LabelInput
        title="API Key"
        value={apiKey}
        onChange={(value) => setApiKey(value)}
        description="Your API key is used to authenticate your requests to the API."
        placeholder="Enter your API key"
        className="w-full"
      />
      <div className="w-full flex justify-center items-center">
        <button
          className="w-[8rem] bg-[#1E0C34] text-[#FFF] rounded-[6px] py-[.75rem] px-[1rem] font-[400] text-[.75rem] mt-[1rem] border-[#965CDE] border-[1px] hover:bg-[#965CDE] hover:text-[#101010] active:bg-[#965CDE] active:text-[#101010] cursor-pointer"
          onClick={handleAdd}
        >
          Add
        </button>
      </div>
    </div>
  );
}

export default APIKey;
