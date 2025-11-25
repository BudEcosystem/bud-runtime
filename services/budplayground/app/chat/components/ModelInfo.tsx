import {Image, Tag } from "antd";
import { useConfig } from "../../context/ConfigContext";
import { useEffect, useState } from "react";
import { getChromeColor } from "../../components/bud/utils/color";
import { Text_14_400_EEEEEE } from "@/lib/text";
import { Text_12_400_757575 } from "@/lib/text";


export default function ModelInfo({deployment}: any){
    const { assetBaseUrl } = useConfig();
    const [imageUrl, setImageUrl] = useState('');
    useEffect(() => {
        console.log(deployment)
        if(deployment?.model?.icon) {
            setImageUrl(assetBaseUrl + deployment?.model?.icon);
        } else if(deployment?.model?.provider?.icon) {
            setImageUrl(assetBaseUrl + deployment?.model?.provider?.icon);
        } else {
            setImageUrl(assetBaseUrl + "/icons/providers/openai.png");
        }
    }, [deployment, assetBaseUrl])


    return(
        <div className="flex flex-col gap-[.5rem] w-full mx-auto max-full h-full justify-center items-center">
            <div className="text-[#B3B3B3] text-[.625rem] font-[400] bg-[#FFFFFF08] border-[1px] border-[#191919] rounded-[10px] md:max-h-[400px] lg:max-h-[500px] xl:max-h-[700px] overflow-auto ">
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
                    <div className="flex flex-col gap-[.5rem] mt-[1.5rem]">
                        <div className="text-[#757575] text-[0.9rem] font-[400] leading-[1.5rem]">
                            {deployment?.model?.description}
                        </div>
                    </div>
                </div>
                {deployment?.model?.model_licenses?.license_type && <div className="py-[0.9rem] px-[1.3rem] border-b-[1px] border-[#1F1F1F]">
                    <div className="flex flex-row gap-[.5rem]">
                        <div className="text-[#EEEEEE] text-[0.8rem] font-[400] w-[150px]">License</div>
                        <div className="text-[#EEEEEE] text-[0.8rem] font-[400]">
                            {deployment?.model?.model_licenses?.license_type}
                        </div>
                    </div>
                </div>}
                <div className="py-[0.9rem] px-[1.3rem] border-b-[1px] border-[#1F1F1F]">
                    <div className="flex flex-row gap-[.5rem]">
                        <div className="text-[#EEEEEE] text-[0.8rem] font-[400] w-[150px]">Context</div>
                        <div className="text-[#EEEEEE] text-[0.8rem] font-[400]">
                            {deployment?.context_length?.toLocaleString()}
                        </div>
                    </div>
                </div>
                {deployment?.input_cost && <div className="py-[0.9rem] px-[1.3rem] border-b-[1px] border-[#1F1F1F]">
                    <div className="flex flex-row gap-[.5rem]">
                        <div className="text-[#EEEEEE] text-[0.8rem] font-[400] w-[150px]">Input Pricing</div>
                        <div className="text-[#EEEEEE] text-[0.8rem] font-[400]">
                            ${(deployment?.input_cost?.input_cost_per_token * 1000000).toFixed(2)} per million tokens
                        </div>
                    </div>
                </div>}
                { deployment?.output_cost && <div className="py-[0.9rem] px-[1.3rem] border-b-[1px] border-[#1F1F1F]">
                    <div className="flex flex-row gap-[.5rem]">
                        <div className="text-[#EEEEEE] text-[0.8rem] font-[400] w-[150px]">Output Pricing</div>
                        <div className="text-[#EEEEEE] text-[0.8rem] font-[400]">
                            ${(deployment?.output_cost?.output_cost_per_token * 1000000).toFixed(2)} per million tokens
                        </div>
                    </div>
                </div>}
                {deployment?.model?.strengths?.length > 0 && (
                <>
                    <div className="pt-[1.5rem] mb-[1.4rem] px-[1.3rem]">
                    <div>
                        <div className="block text-[0.875rem] font-[400] text-[#EEEEEE] mb-[.5rem]">Model is Great at</div>
                        <div className="block text-[0.75rem] font-normal text-[#757575]">Following is the list of things model is really good at doing</div>
                    </div>
                    <ul className="custom-bullet-list mt-[.9rem]">
                        {deployment?.model?.strengths?.map((item: any, index: any) => (
                        <li key={index}>
                            <div className="block text-[0.875rem] font-[400] text-[#EEEEEE]">{item}</div>
                        </li>
                        ))}
                    </ul>
                    </div>
                    <div className="hR"></div>
                </>
                )}
                {deployment?.model?.limitations?.length > 0 && (
                <>
                    <div className="pt-[1.5rem] mb-[1.4rem] px-[1.3rem]">
                    <div>
                        <div className="block text-[0.875rem] font-[400] text-[#EEEEEE] mb-[.5rem]">Model is Not Good With</div>
                        <div className="block text-[0.75rem] font-normal text-[#757575]">Following is the list of things model is not great at</div>
                    </div>
                    <ul className="custom-bullet-list mt-[.9rem]">
                        {deployment?.model?.limitations?.map((item: any, index: any) => (
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
