import { Input, Image } from 'antd'
import React from 'react'
import IslandIcon from '../island/IslandIcon'
import EmbeddedIframe from 'src/pages/home/playground/iFrame'

function BudChat() {
    return (
        <div className='relative flex flex-col w-full h-full'>

            <EmbeddedIframe singleChat={true} />

            {/* <div className='flex flex-col w-full h-full bg-[#101010] justify-center items-center'>
                <div className='bud-icon' />
            </div>

            <div>
                <Input
                    className='height-52'
                    prefix={<IslandIcon size='1.1875rem' />}
                    defaultValue=""
                    placeholder='Ask Bud'
                    suffix={<Image preview={false} style={{width: 'auto', height: 'auto'}} src='/sendicon.svg' alt='' />}
                />
            </div> */}

        </div>
    )
}

export default BudChat
