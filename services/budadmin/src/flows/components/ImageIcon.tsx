import { assetBaseUrl } from '@/components/environment'
import { Flex, Image } from 'antd'
import React from 'react'

export default function ImageIcon({ icon,
    width = '1.600625rem',
    height = 'auto',
}: {
    icon: string,
    width?: string,
    height?: string
}) {
    return icon?.length > 2 ?
        <Image
            preview={false}
            className="mainLogo"
            src={assetBaseUrl + icon}
            style={{ width, height }}
            alt="Logo"
        /> : <Flex
            align={"center"}
            justify={"center"}
            className="bg-[#1F1F1F] w-[2.40125rem] h-[2.40125rem] rounded"
        >
            <div className="text-[1.5625rem]">
                {icon}
            </div>
        </Flex>
}
