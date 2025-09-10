// Tag color helpers

const colourOptions = [
  { value: "#EEEEEE", label: "Light Grey" },
  { value: "#965CDE", label: "Purple" },
  { value: "#EC7575", label: "Red" },
  { value: "#479D5F", label: "Green" },
  { value: "#D1B854", label: "Yellow" },
  { value: "#ECAE75", label: "Orange" },
  { value: "#42CACF", label: "Cyan" },
  { value: "#DE5CD1", label: "Pink" },
  { value: "#4077E6", label: "Blue" },
  { value: "#8DE640", label: "Lime" },
  { value: "#8E5EFF", label: "Violet" },
  { value: "#FF895E", label: "Salmon" },
  { value: "#FF5E99", label: "Pink" },
  { value: "#F4FF5E", label: "Yellow" },
  { value: "#FF5E5E", label: "Red" },
  { value: "#5EA3FF", label: "Blue" },
  { value: "#5EFFBE", label: "Green" },
  { value: "#757575", label: "Grey" },
  { value: "#B3B3B3", label: "White" },
  { value: "#3EC564", label: "Available" },
  { value: "#666666", label: "Gray40" },
];

export function checkColor(color: string) {
  return colourOptions.find((option) => option.value === color);
}

export function getChromeColor(color: string) {
  try {
    // Convert hex to rgba with 0.1 opacity
    const hex = color.replace("#", "");
    const r = parseInt(hex.substring(0, 2), 16);
    const g = parseInt(hex.substring(2, 4), 16);
    const b = parseInt(hex.substring(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, 0.1)`;
  } catch (error) {
    return "transparent";
  }
}
