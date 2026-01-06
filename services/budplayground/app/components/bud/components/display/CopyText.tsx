import { useEffect, useState, useRef } from "react";
import { copyToClipboard } from "../../../../utils/clipboard";


export function CopyText(props: { text: string }) {
    const textRef = useRef(props.text);
    const [copied, setCopied] = useState(false);

    // Keep ref in sync with props
    useEffect(() => {
        textRef.current = props.text;
    }, [props.text]);

    const handleCopy = async () => {
        const textToCopy = textRef.current || props.text;
        await copyToClipboard(textToCopy, {
            onSuccess: () => setCopied(true),
            onError: (error: Error) => console.error('Failed to copy:', error),
        });
    }

    useEffect(() => {
        if (copied) {
            setTimeout(() => {
                setCopied(false);
            }, 1000);
        }
    }, [copied]);

    return (
    <div
      className="relative w-[1rem] h-[1rem] flex justify-center items-center cursor-pointer group text-[#B3B3B3] hover:text-[#FFFFFF]"
      onClick={() => handleCopy()}
    >
        <svg
            xmlns="http://www.w3.org/2000/svg"
            width="12"
            height="15"
            fill="none"
        >
            <path
            fill="currentColor"
            fillRule="evenodd"
            d="M.8 9.498a1.2 1.2 0 0 0 1.2 1.2h1.2v1.595a1.2 1.2 0 0 0 1.2 1.2H10a1.2 1.2 0 0 0 1.2-1.2v-6.8a1.2 1.2 0 0 0-1.2-1.2H4.4a1.2 1.2 0 0 0-1.2 1.2v4.405H2a.4.4 0 0 1-.4-.4v-6.8c0-.22.18-.4.4-.4h5.6c.221 0 .4.18.4.4v1.534h.8V2.698a1.2 1.2 0 0 0-1.2-1.2H2a1.2 1.2 0 0 0-1.2 1.2v6.8ZM4 5.493c0-.221.18-.4.4-.4H10c.221 0 .4.179.4.4v6.8a.4.4 0 0 1-.4.4H4.4a.4.4 0 0 1-.4-.4v-6.8Z"
            clipRule="evenodd"
            />
        </svg>
        {copied && <div className="absolute bottom-5 right-[-15] bg-[#0d0d0d] px-2 py-1 border border-[#262626] rounded-[.25rem] text-white">Copied</div>}
    </div>
  );
}
