import { useEffect, useState } from "react";

interface FileViewerProps {
  fileUrl?: string;
}

const FileViewer: React.FC<FileViewerProps> = ({ fileUrl }) => {
  const [fileType, setFileType] = useState("");
  const [textContent, setTextContent] = useState("");
  const [blobUrl, setBlobUrl] = useState("");

  useEffect(() => {
    const fetchFileType = async () => {
      try {
        const res = await fetch(fileUrl);
        const contentType = res.headers.get("Content-Type") || "";
        console.log("Content-Type:", contentType);
        if (!res.ok) throw new Error("Failed to fetch file");

        const url = fileUrl || "";

        // Use URL extension fallback if contentType is useless
        if (contentType.startsWith("image/")) {
          setFileType("image");
          setBlobUrl(url);
        } else if (contentType === "application/pdf" || url.endsWith(".pdf")) {
          setFileType("pdf");
          setBlobUrl(url);
        } else if (contentType.includes("text/html") || url.endsWith(".html")) {
          setFileType("html");
          setBlobUrl(url);
        } else if (
          contentType.startsWith("text/") ||
          url.endsWith(".md") ||
          url.endsWith(".txt") ||
          contentType === "application/octet-stream" // Fallback for unknown but readable files
        ) {
          setFileType("text");
          const text = await res.text(); // Try to parse it as text anyway
          setTextContent(text);
        } else {
          setFileType("unknown");
        }
      } catch (error) {
        console.error("File load error:", error);
        setFileType("error");
      }
    };

    if (fileUrl) {
      fetchFileType();
    }
  }, [fileUrl]);

  if (fileType === "image") {
    return (
      <img
        src={blobUrl}
        alt="Image Preview"
        className="max-w-full h-auto rounded"
      />
    );
  }

  if (fileType === "pdf") {
    return (
      <iframe
        style={{ backgroundColor: "transparent" }}
        src={blobUrl}
        title="PDF Viewer"
        width="100%"
        height="600px"
        className="border rounded"
      />
    );
  }

  if (fileType === "html") {
    return (
      <iframe
        style={{ backgroundColor: "transparent" }}
        src={blobUrl}
        // src={fileUrl}
        title="HTML Viewer"
        width="100%"
        height="600px"
        className="border rounded"
      />
    );
  }

  if (fileType === "text") {
    return (
      <pre className="whitespace-pre-wrap p-4 bg-[#202020] rounded overflow-auto text-[#EEEEEE] text-[.625rem]">
        {textContent}
      </pre>
    );
  }

  if (fileType === "error") {
    return <div className="text-red-500">Failed to load file</div>;
  }

  return (
    <a
      href={fileUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="text-blue-600 underline"
    >
      Open file
    </a>
  );
};

export default FileViewer;
