import React, { useCallback, useState } from "react";
import { Upload } from "antd";
import { Text_12_400_B3B3B3, Text_14_400_EEEEEE } from "@/components/ui/text";
import { SecondaryButton } from "@/components/ui/bud/form/Buttons";

const { Dragger } = Upload;

interface DragDropUploadProps {
  onFileSelect: (file: File) => void;
  accept?: string;
  maxSize?: number; // in MB
  title?: string;
  description?: string;
  className?: string;
  selectedFile?: File | null; // Optional external file state
}

export default function DragDropUpload({
  onFileSelect,
  accept = ".json,.yaml,.yml",
  maxSize = 10,
  title = "Drag and drop your OpenAPI file here, or click to browse",
  description,
  className = "",
  selectedFile: externalSelectedFile,
}: DragDropUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [internalSelectedFile, setInternalSelectedFile] = useState<File | null>(null);

  // Use external file if provided, otherwise use internal state
  const selectedFile = externalSelectedFile !== undefined ? externalSelectedFile : internalSelectedFile;
  const setSelectedFile = (file: File | null) => {
    setInternalSelectedFile(file);
  };

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);

      const files = e.dataTransfer.files;
      if (files.length > 0) {
        const file = files[0];
        if (file.size <= maxSize * 1024 * 1024) {
          setSelectedFile(file);
          onFileSelect(file);
        }
      }
    },
    [maxSize, onFileSelect]
  );

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        const file = files[0];
        if (file.size <= maxSize * 1024 * 1024) {
          setSelectedFile(file);
          onFileSelect(file);
        }
      }
    },
    [maxSize, onFileSelect]
  );

  const handleChooseFile = () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = accept;
    input.onchange = (e) => {
      const target = e.target as HTMLInputElement;
      if (target.files && target.files.length > 0) {
        const file = target.files[0];
        if (file.size <= maxSize * 1024 * 1024) {
          setSelectedFile(file);
          onFileSelect(file);
        }
      }
    };
    input.click();
  };

  return (
    <div
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      className={`border-2 border-dashed rounded-lg p-8 text-center transition-all cursor-pointer ${
        isDragging
          ? "border-[#965CDE] bg-[#965CDE]/10"
          : "border-[#3F3F3F] hover:border-[#757575]"
      } ${className}`}
      onClick={handleChooseFile}
    >
      {/* File Icon */}
      <div className="flex justify-center mb-4">
        <svg
          width="48"
          height="48"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="text-[#757575]"
        >
          <path
            d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M14 2V8H20"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M12 18V12"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M9 15L12 12L15 15"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>

      {/* Title */}
      {selectedFile ? (
        <Text_14_400_EEEEEE className="mb-2">
          {selectedFile.name}
        </Text_14_400_EEEEEE>
      ) : (
        <Text_14_400_EEEEEE className="mb-2">{title}</Text_14_400_EEEEEE>
      )}

      {/* Description */}
      {description && (
        <Text_12_400_B3B3B3 className="mb-4">{description}</Text_12_400_B3B3B3>
      )}

      {/* Choose File Button */}
      <div className="mt-4" onClick={(e) => e.stopPropagation()}>
        <SecondaryButton onClick={handleChooseFile}>
          Choose File
        </SecondaryButton>
      </div>
    </div>
  );
}
