import { Flex } from 'antd'
import React from 'react'

export default function BackButton({
    onClick,
    classNames
}: {
    onClick: () => void,
    classNames?: string
}) {
    return (
        <div
            className={`rounded rounded-full w-[1.125rem] h-[1.125rem] shadow-[0_0_2px_2px_rgba(0, 0, 0, 0.85))] hover:border hover:border-[#120f0f] cursor-pointer mr-[1.25rem] flex justify-center items-center ${classNames}`}
            style={{
                background: '#18191B',
            }}
            onClick={onClick}
        >
            <svg xmlns="http://www.w3.org/2000/svg"
                className="h-[.5rem] w-[.5rem]"
                viewBox="0 0 5 8" fill="none">
                <path d="M4.31863 0.789062L1.07141 4.03629L4.31863 7.28351" stroke="#EEEEEE" strokeWidth="1.11128" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
        </div>
    )
}
