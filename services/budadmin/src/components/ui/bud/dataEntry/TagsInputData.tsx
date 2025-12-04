import { StylesConfig } from "react-select";
import chroma from "chroma-js";

export interface ColourOption {
  readonly value: string;
  readonly label: string;
}

const COLOR_1 = "#EEEEEE";
const COLOR_2 = "#965CDE";
const COLOR_3 = "#EC7575";
const COLOR_4 = "#479D5F";
const COLOR_5 = "#D1B854";
const COLOR_6 = "#ECAE75";
const COLOR_7 = "#42CACF";
const COLOR_8 = "#DE5CD1";
const COLOR_9 = "#4077E6";
const COLOR_10 = "#8DE640";
const COLOR_11 = "#8E5EFF";
const COLOR_12 = "#FF895E";
const COLOR_13 = "#FF5E99";
const COLOR_14 = "#F4FF5E";
const COLOR_15 = "#FF5E5E";
const COLOR_16 = "#5EA3FF";
const COLOR_17 = "#5EFFBE";
const COLOR_18 = "#757575";
const COLOR_19 = "#B3B3B3";
const COLOR_20 = "#666666";

export const colourOptions = [
  { value: COLOR_1, label: "Light Grey" },
  { value: COLOR_2, label: "Purple" },
  { value: COLOR_3, label: "Red" },
  { value: COLOR_4, label: "Green" },
  { value: COLOR_5, label: "Yellow" },
  { value: COLOR_6, label: "Orange" },
  { value: COLOR_7, label: "Cyan" },
  { value: COLOR_8, label: "Pink" },
  { value: COLOR_9, label: "Blue" },
  { value: COLOR_10, label: "Lime" },
  { value: COLOR_11, label: "Violet" },
  { value: COLOR_12, label: "Salmon" },
  { value: COLOR_13, label: "Pink" },
  { value: COLOR_14, label: "Yellow" },
  { value: COLOR_15, label: "Red" },
  { value: COLOR_16, label: "Blue" },
  { value: COLOR_17, label: "Green" },
  { value: COLOR_18, label: "Grey" },
  { value: COLOR_19, label: "White" },
  { value: "#3EC564", label: "Available" },
  { value: COLOR_20, label: "Gray40" },
];

export const colourStyles = (
  overrides: any = {},
): StylesConfig<ColourOption, true> => {
  return {
    control: (styles) => ({
      ...styles,
      backgroundColor: "transparent",
      borderWidth: 1,
      borderColor: "#757575",
      boxShadow: "none",
      padding: ".75rem 0",
      "&:hover": {
        borderColor: "#CFCFCF",
      },
      borderRadius: "6px",
      ...overrides.control,
    }),
    indicatorSeparator: (styles) => ({
      ...styles,
      display: "none",
      ...overrides.indicatorSeparator,
    }),
    clearIndicator: (styles) => ({
      ...styles,
      display: "none",
      ...overrides.clearIndicator,
    }),
    container: (state) => ({
      ...state,
      backgroundColor: "#1F1F1F",
      ...overrides.container,
    }),
    menu: (styles) => ({
      ...styles,
      backgroundColor: "#161616",
      marginTop: ".4rem",
      backdropFilter: "blur(4px)",
      border: "1px solid #1F1F1F",
      ...overrides.menu,
      zIndex: 9999,
    }),
    option: (styles, { data, isDisabled, isFocused, isSelected }) => {
      let color = chroma("#FFF");
      try {
        color = chroma(data.value);
      } catch (error) {}
      return {
        ...styles,
        backgroundColor: isDisabled
          ? undefined
          : isSelected
            ? data.value
            : isFocused
              ? color.alpha(0.1).css()
              : undefined,
        color: isDisabled
          ? "#ccc"
          : isSelected
            ? chroma.contrast(color, "white") > 2
              ? "white"
              : "black"
            : data.value,
        cursor: isDisabled ? "not-allowed" : "default",
        ":active": {
          ...styles[":active"],
          backgroundColor: !isDisabled
            ? isSelected
              ? data.value
              : color.alpha(0.3).css()
            : undefined,
        },
        ...overrides.option,
      };
    },
    multiValue: (styles, { data }) => {
      return {
        ...styles,
        backgroundColor: getChromeColor(data.value || COLOR_5),
        ...overrides.multiValue,
      };
    },
    multiValueLabel: (styles, { data }) => ({
      ...styles,
      fontWeight: 500,
      color: data.value,
      paddingLeft: 3,
      ...overrides.multiValueLabel,
    }),
    multiValueRemove: (styles, { data }) => ({
      ...styles,
      color: data.value,
      ":hover": {
        backgroundColor: getChromeColor(data.value),
        color: data.value,
      },
      ...overrides.multiValueRemove,
    }),
    menuList: (styles) => ({
      ...styles,
      padding: 8,
      borderRadius: 6,
      // backgroundColor: "#101010",
      maxHeight: (() => {
        if (window.innerWidth > 1900) return 170;
        if (window.innerWidth > 1600) return 135;
        return 130;
      })(),
      overflowY: "auto",
      ...overrides.menuList,
    }),
    dropdownIndicator: (styles) => ({
      ...styles,
      display: "none",
      ...overrides.dropdownIndicator,
    }),
  };
};

export function randomColor() {
  return colourOptions[Math.floor(Math.random() * colourOptions.length)];
}

export function checkColor(color: string) {
  // Return undefined for missing/empty colors (will fallback to default #D1B854)
  if (!color || color.trim() === "") return undefined;

  // First check if it's a predefined color
  const predefinedColor = colourOptions.find((option) => option.value === color);
  if (predefinedColor) return predefinedColor;

  // If not predefined, validate if it's a valid color using chroma.js
  try {
    chroma(color);
    return { value: color, label: "Custom" };
  } catch {
    return undefined;
  }
}

export function getChromeColor(color: string) {
  try {
    return chroma(color).alpha(0.1).css();
  } catch (error) {
    return "transparent";
  }
}

export function getChromeColorHex(color: string, alpha?: number): string {
  try {
    // Return a hex code with alpha (e.g. "#RRGGBBAA")
    return chroma(color)
      .alpha(alpha || 0.1)
      .css("hex8");
  } catch (error) {
    return "transparent";
  }
}
