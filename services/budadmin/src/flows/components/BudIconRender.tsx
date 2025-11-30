import { assetBaseUrl } from "@/components/environment";
import { pxToRem } from "@/components/ui/text";
import { Image } from "antd";

export default function IconRender({
  icon,
  size,
  imageSize,
  type,
  model,
}: {
  icon: string;
  size?: number;
  imageSize?: number;
  type?: string;
  model?: any;
}) {
  const remSize = pxToRem(size || 28);
  const imageRemSize = pxToRem(imageSize || 18);
  const iconImage = icon ? `${assetBaseUrl}${icon}` : (type == "hugging_face" || type == "cloud_model") && model
      ? `${assetBaseUrl}${model?.provider.icon}`
      : "";
  if (icon?.length <= 3) {
    return (
      <div
        className=" bg-[#1F1F1F] rounded-[.4rem]  flex items-center justify-center"
        style={{
          width: remSize,
          height: remSize,
          minWidth: remSize,
          maxWidth: remSize,
          minHeight: remSize,
          maxHeight: remSize,
        }}
      >
        <div style={{ fontSize: imageRemSize }}>{icon}</div>
      </div>
    );
  }

  return (
    <div
      className=" bg-[#1F1F1F] rounded-[.4rem]  flex items-center justify-center"
      style={{
        width: remSize,
        height: remSize,
        minWidth: remSize,
        maxWidth: remSize,
        minHeight: remSize,
        maxHeight: remSize,
      }}
    >
      <Image
        preview={false}
        src={
          iconImage ||
          (type === "url"
            ? "/images/drawer/url-2.png"
            : "/images/drawer/disk-2.png")
        }
        alt="info"
        style={{ width: imageRemSize, height: imageRemSize }}
      />
    </div>
  );
}

export function IconOnlyRender({
  icon,
  size,
  imageSize,
  type,
  model,
}: {
  icon: string;
  size?: number;
  imageSize?: number;
  type?: string;
  model?: any;
}) {
  const remSize = pxToRem(size || 28);
  const imageRemSize = pxToRem(imageSize || 18);
  const iconImage = icon
    ? `${assetBaseUrl}${icon}`
    : (type == "hugging_face" || type == "cloud_model") && model
      ? `${assetBaseUrl}${model?.provider.icon}`
      : "";
  if (icon?.length <= 3) {
    return (
      <div
        className="h-[100%] leading-[100%] flex justify-center items-center"
        style={{ fontSize: imageRemSize }}
      >
        {icon}
      </div>
    );
  }

  return (
    <div className="w-full h-full rounded-[.4rem]  flex items-center justify-center">
      <Image
        preview={false}
        src={
          iconImage ||
          (type === "url"
            ? "/images/drawer/url-2.png"
            : "/images/drawer/disk-2.png")
        }
        alt="info"
        style={{ width: imageRemSize, height: imageRemSize }}
      />
    </div>
  );
}
