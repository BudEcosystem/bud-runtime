import {Image, Tag } from "antd";
import { assetBaseUrl } from "../environment";
import { useEffect, useState } from "react";
import { getChromeColor } from "../utils/color";
import { Text_14_400_EEEEEE } from "@/lib/text";
import { Text_12_400_757575 } from "@/lib/text";


export default function ModelInfo({deployment}: any){
    const [imageUrl, setImageUrl] = useState(assetBaseUrl + deployment?.model?.icon);
    useEffect(() => {
        console.log(deployment)
        if(deployment?.model?.icon) {
            setImageUrl(assetBaseUrl + deployment?.model?.icon);
        } else if(deployment?.model?.provider?.icon) {
            setImageUrl(assetBaseUrl + deployment?.model?.provider?.icon);
        } else {
            setImageUrl(assetBaseUrl + "/icons/providers/openai.png");
        }
    }, [])

    const strengths = [
        "Supports 128k token context length, enabling handling of lengthy documents and complex tasks requiring extensive context.",
        "Achieves strong performance on benchmarks such as MMLU (69.4 for 8B Instruct), GSM8K (84.5 for 8B Instruct), and HumanEval (72.6 for 8B Instruct), demonstrating robust reasoning and coding capabilities.",
        "Multilingual support for 8 languages (e.g., English, German, French) with instruction-tuned versions optimized for dialogue and tool use cases.",
        "Uses Grouped-Query Attention (GQA) for improved inference scalability and efficiency.",
        "Includes safety tools like Llama Guard 3 and Prompt Guard to mitigate risks in deployment."
      ]
    const limitations = [
        "Requires significant computational resources, with the 405B version needing 30.84M GPU hours and H100-80GB GPUs for training.",
        "Commercial users with >700M monthly active users must obtain a separate license from Meta.",
        "Limited official support for languages beyond the 8 listed; fine-tuning for other languages requires careful safety considerations.",
        "Some benchmarks show moderate performance, such as the Gorilla Benchmark API Bench (35.3 for 405B Instruct) and Multilingual MGSM (68.9 for 8B Instruct)."
      ]

    return(
        <div className="flex flex-col gap-[.5rem] w-full mx-auto max-w-2xl h-full justify-center items-center">
            <div className="text-[#B3B3B3] text-[.625rem] font-[400] w-[500px] bg-[#FFFFFF08] border-[1px] border-[#1F1F1F] rounded-[10px] max-h-[500px] overflow-auto ">
                <div className="p-[1.3rem]">
                    <div className="flex flex-row gap-[.5rem]">
                        <div className=" w-[2.68rem] h-[2.68rem] flex justify-center items-center shrink-0 grow-0 bg-[#1F1F1F] rounded-[6px] p-[.25rem] mt-[.25rem]">
                            <Image
                                preview={false}
                                src={imageUrl}
                                fallback={"/icons/modelRepoWhite.png"}
                                alt="info"
                                style={{ width: '1.625rem', height: '1.625rem' }}
                            />
                        </div>
                        <div className="flex flex-col ml-[.5rem]">
                            <div className="text-[#EEEEEE] text-[0.9rem] font-[400]">{deployment?.model?.name}</div>
                            <div className="text-[#757575] w-full overflow-hidden text-ellipsis text-xs mt-[0.25rem] flex">
                                {deployment?.model?.tags.map((tag: any) => (
                                    <Tag
                                    key={tag.name}
                                    className=" !text-[.625rem] font-[400] rounded-[0.5rem] !px-[.375rem] !h-[1.25rem] flex items-center justify-center leading-[1.25rem]"
                                    style={{
                                        background: getChromeColor(tag.color || "#D1B854"),
                                        borderColor: getChromeColor(tag.color || "#D1B854"),
                                        color: tag.color || "#D1B854",
                                    }}
                                    >
                                    {tag.name}
                                    </Tag>
                                ))}
                            </div>
                        </div>
                    </div>
                    <div className="flex flex-col gap-[.5rem] mt-[1rem]">
                        <div className="text-[#757575] text-[0.8rem] font-[400]">
                            {deployment?.model?.description}
                        </div>
                    </div>
                </div>
                <div className="py-[0.9rem] px-[1.3rem] border-b-[1px] border-[#1F1F1F]">
                    <div className="flex flex-row gap-[.5rem]">
                        <div className="text-[#EEEEEE] text-[0.8rem] font-[400] w-[150px]">Context</div>
                        <div className="text-[#EEEEEE] text-[0.8rem] font-[400]">
                            {deployment?.context_length}
                        </div>
                    </div>
                </div>
                {deployment?.input_cost && <div className="py-[0.9rem] px-[1.3rem] border-b-[1px] border-[#1F1F1F]">
                    <div className="flex flex-row gap-[.5rem]">
                        <div className="text-[#EEEEEE] text-[0.8rem] font-[400] w-[150px]">Input Pricing</div>
                        <div className="text-[#EEEEEE] text-[0.8rem] font-[400]">
                            ${deployment?.input_cost} / million tokens
                        </div>
                    </div>
                </div>}
                { deployment?.output_cost && <div className="py-[0.9rem] px-[1.3rem] border-b-[1px] border-[#1F1F1F]">
                    <div className="flex flex-row gap-[.5rem]">
                        <div className="text-[#EEEEEE] text-[0.8rem] font-[400] w-[150px]">Output Pricing</div>
                        <div className="text-[#EEEEEE] text-[0.8rem] font-[400]">
                            ${deployment?.output_cost} / million tokens
                        </div>
                    </div>
                </div>}
                {strengths.length > 0 && (
                <>
                    <div className="pt-[1.5rem] mb-[1.4rem] px-[1.3rem]">
                    <div>
                        <div className="block text-[0.875rem] font-[400] text-[#EEEEEE]">Model is Great at</div>
                        <div className="block text-[0.75rem] font-normal text-[#757575]">Following is the list of things model is really good at doing</div>
                    </div>
                    <ul className="custom-bullet-list mt-[.9rem]">
                        {strengths?.map((item, index) => (
                        <li key={index}>
                            <div className="block text-[0.875rem] font-[400] text-[#EEEEEE]">{item}</div>
                        </li>
                        ))}
                    </ul>
                    </div>
                    <div className="hR"></div>
                </>
                )}
                {limitations.length > 0 && (
                <>
                    <div className="pt-[1.5rem] mb-[1.4rem] px-[1.3rem]">
                    <div>
                        <div className="block text-[0.875rem] font-[400] text-[#EEEEEE]">Model is Not Good With</div>
                        <div className="block text-[0.75rem] font-normal text-[#757575]">Following is the list of things model is not great at</div>
                    </div>
                    <ul className="custom-bullet-list mt-[.9rem]">
                        {limitations?.map((item, index) => (
                        <li key={index}>
                            <div className="block text-[0.875rem] font-[400] text-[#EEEEEE]">{item}</div>
                        </li>

                        ))}
                    </ul>
                    </div>
                    <div className="hR"></div>
                </>
                )}
            </div>
        </div>
    )
}