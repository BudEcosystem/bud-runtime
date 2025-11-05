import chroma from "chroma-js";

export function getChromeColor(color: string) {
    try {
        return chroma(color).alpha(0.1).css();
    } catch (error) {
        return "transparent";
    }
}
