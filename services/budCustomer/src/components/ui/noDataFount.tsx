import React from 'react';
import { Image } from 'antd';

interface NoDataFountProps {
  message?: string;
  imageUrl?: string;
  className?: string;
}

const NoDataFount: React.FC<NoDataFountProps> = ({
  message = "No data found",
  imageUrl = "/images/nodataBud.png",
  className = "",
}) => {
  return (
    <div className={`flex flex-col items-center justify-center py-8 ${className}`}>
      <Image
        src={imageUrl}
        alt="No data"
        width={120}
        height={120}
        preview={false}
        className="opacity-60 mb-4"
      />
      <p className="text-gray-400 text-sm">{message}</p>
    </div>
  );
};

export default NoDataFount;