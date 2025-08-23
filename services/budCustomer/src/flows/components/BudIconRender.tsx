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

  // Handle emoji icons (short strings)
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

  // Build icon URL with proper handling
  let iconImage = "";
  if (icon) {
    // If icon starts with http/https, use it directly
    if (icon.startsWith("http://") || icon.startsWith("https://")) {
      iconImage = icon;
    } else if (icon.startsWith("/")) {
      // If it starts with /, it's a local asset
      iconImage = icon;
    } else if (assetBaseUrl) {
      // Only use assetBaseUrl if it's configured
      iconImage = `${assetBaseUrl}${icon.startsWith("/") ? icon : "/" + icon}`;
    }
  } else if ((type === "hugging_face" || type === "cloud_model") && model?.provider?.icon) {
    if (model.provider.icon.startsWith("http://") || model.provider.icon.startsWith("https://")) {
      iconImage = model.provider.icon;
    } else if (model.provider.icon.startsWith("/")) {
      iconImage = model.provider.icon;
    } else if (assetBaseUrl) {
      iconImage = `${assetBaseUrl}${model.provider.icon.startsWith("/") ? model.provider.icon : "/" + model.provider.icon}`;
    }
  }

  // Fallback to local images if no icon URL
  const fallbackImage = type === "url" ? "/images/drawer/url-2.png" : "/images/drawer/disk-2.png";

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
        src={iconImage || fallbackImage}
        alt="info"
        style={{ width: imageRemSize, height: imageRemSize }}
        onError={(e) => {
          // Fallback on error
          e.currentTarget.src = fallbackImage;
        }}
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

  // Handle emoji icons (short strings)
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

  // Build icon URL with proper handling
  let iconImage = "";
  if (icon) {
    // If icon starts with http/https, use it directly
    if (icon.startsWith("http://") || icon.startsWith("https://")) {
      iconImage = icon;
    } else if (icon.startsWith("/")) {
      // If it starts with /, it's a local asset
      iconImage = icon;
    } else if (assetBaseUrl) {
      // Only use assetBaseUrl if it's configured
      iconImage = `${assetBaseUrl}${icon.startsWith("/") ? icon : "/" + icon}`;
    }
  } else if ((type === "hugging_face" || type === "cloud_model") && model?.provider?.icon) {
    if (model.provider.icon.startsWith("http://") || model.provider.icon.startsWith("https://")) {
      iconImage = model.provider.icon;
    } else if (model.provider.icon.startsWith("/")) {
      iconImage = model.provider.icon;
    } else if (assetBaseUrl) {
      iconImage = `${assetBaseUrl}${model.provider.icon.startsWith("/") ? model.provider.icon : "/" + model.provider.icon}`;
    }
  }

  // Fallback to local images if no icon URL
  const fallbackImage = type === "url" ? "/images/drawer/url-2.png" : "/images/drawer/disk-2.png";

  return (
    <div className="w-full h-full rounded-[.4rem]  flex items-center justify-center">
      <Image
        preview={false}
        src={iconImage || fallbackImage}
        alt="info"
        style={{ width: imageRemSize, height: imageRemSize }}
        onError={(e) => {
          // Fallback on error
          e.currentTarget.src = fallbackImage;
        }}
      />
    </div>
  );
}
