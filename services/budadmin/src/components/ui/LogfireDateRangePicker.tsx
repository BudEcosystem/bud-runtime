import React, { useState, useEffect, useMemo } from "react";
import { DatePicker, ConfigProvider, Popover } from "antd";
import { Calendar, ChevronDown } from "lucide-react";
import dayjs from "dayjs";
import type { Dayjs } from "dayjs";
import {
  Text_10_400_B3B3B3,
  Text_10_600_EEEEEE,
  Text_12_400_757575,
  Text_12_400_EEEEEE,
  Text_12_600_EEEEEE,
} from "@/components/ui/text";

const { RangePicker } = DatePicker;

// Preset time range options matching Logfire
interface PresetOption {
  label: string;
  value: string; // e.g., "5m", "15m", "1h"
  getDates: () => [Dayjs, Dayjs];
}

const PRESET_OPTIONS: PresetOption[] = [
  {
    label: "Last 5 minutes",
    value: "5m",
    getDates: () => [dayjs().subtract(5, "minutes"), dayjs()],
  },
  {
    label: "Last 15 minutes",
    value: "15m",
    getDates: () => [dayjs().subtract(15, "minutes"), dayjs()],
  },
  {
    label: "Last 30 minutes",
    value: "30m",
    getDates: () => [dayjs().subtract(30, "minutes"), dayjs()],
  },
  {
    label: "Last hour",
    value: "1h",
    getDates: () => [dayjs().subtract(1, "hour"), dayjs()],
  },
  {
    label: "Last 6 hours",
    value: "6h",
    getDates: () => [dayjs().subtract(6, "hours"), dayjs()],
  },
  {
    label: "Last 12 hours",
    value: "12h",
    getDates: () => [dayjs().subtract(12, "hours"), dayjs()],
  },
  {
    label: "Last day",
    value: "24h",
    getDates: () => [dayjs().subtract(1, "day"), dayjs()],
  },
  {
    label: "Last 2 days",
    value: "2d",
    getDates: () => [dayjs().subtract(2, "days"), dayjs()],
  },
  {
    label: "Last 7 days",
    value: "7d",
    getDates: () => [dayjs().subtract(7, "days"), dayjs()],
  },
  {
    label: "Last 14 days",
    value: "14d",
    getDates: () => [dayjs().subtract(14, "days"), dayjs()],
  },
  {
    label: "Last 30 days",
    value: "30d",
    getDates: () => [dayjs().subtract(30, "days"), dayjs()],
  },
];

// Map preset values to labels for display
const PRESET_LABEL_MAP: Record<string, string> = PRESET_OPTIONS.reduce(
  (acc, opt) => {
    acc[opt.value] = opt.label;
    return acc;
  },
  {} as Record<string, string>
);

export interface DateRangeValue {
  // For preset mode
  preset?: string;
  // For custom mode
  startDate?: Dayjs;
  endDate?: Dayjs;
}

export interface LogfireDateRangePickerProps {
  value?: DateRangeValue;
  onChange?: (value: DateRangeValue) => void;
  // For backward compatibility with simple string presets
  presetValue?: string;
  onPresetChange?: (preset: string) => void;
  // Custom date range change
  onCustomRangeChange?: (startDate: Dayjs, endDate: Dayjs) => void;
  className?: string;
}

const LogfireDateRangePicker: React.FC<LogfireDateRangePickerProps> = ({
  value,
  onChange,
  presetValue,
  onPresetChange,
  onCustomRangeChange,
  className = "",
}) => {
  const [open, setOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<"preset" | "custom">("preset");

  // Internal state for the picker
  const [selectedPreset, setSelectedPreset] = useState<string>(
    presetValue || value?.preset || "5m"
  );
  const [customRange, setCustomRange] = useState<[Dayjs, Dayjs] | null>(
    value?.startDate && value?.endDate
      ? [value.startDate, value.endDate]
      : null
  );

  // Track if using custom range
  const [isCustom, setIsCustom] = useState(
    !!(value?.startDate && value?.endDate && !value?.preset)
  );

  // Sync with external value changes
  useEffect(() => {
    if (presetValue) {
      setSelectedPreset(presetValue);
      setIsCustom(false);
    }
  }, [presetValue]);

  useEffect(() => {
    if (value?.preset) {
      setSelectedPreset(value.preset);
      setIsCustom(false);
    } else if (value?.startDate && value?.endDate) {
      setCustomRange([value.startDate, value.endDate]);
      setIsCustom(true);
    }
  }, [value]);

  // Get display text for the trigger button
  const displayText = useMemo(() => {
    if (isCustom && customRange) {
      const [start, end] = customRange;
      return `${start.format("MMM D, HH:mm:ss")} - ${end.format("MMM D, HH:mm:ss")}`;
    }
    return PRESET_LABEL_MAP[selectedPreset] || "Last 5 minutes";
  }, [isCustom, customRange, selectedPreset]);

  // Handle preset selection
  const handlePresetSelect = (preset: PresetOption) => {
    setSelectedPreset(preset.value);
    setIsCustom(false);
    setOpen(false);

    // Emit changes
    if (onPresetChange) {
      onPresetChange(preset.value);
    }
    if (onChange) {
      onChange({ preset: preset.value });
    }
  };

  // Handle custom range selection
  const handleCustomRangeChange = (
    dates: [Dayjs | null, Dayjs | null] | null
  ) => {
    if (dates && dates[0] && dates[1]) {
      setCustomRange([dates[0], dates[1]]);
    }
  };

  // Handle Select button click in custom range mode
  const handleSelectCustomRange = () => {
    if (customRange) {
      setIsCustom(true);
      setOpen(false);

      if (onCustomRangeChange) {
        onCustomRangeChange(customRange[0], customRange[1]);
      }
      if (onChange) {
        onChange({ startDate: customRange[0], endDate: customRange[1] });
      }
    }
  };

  // Get current timezone display
  const timezone = useMemo(() => {
    const offset = new Date().getTimezoneOffset();
    const hours = Math.abs(Math.floor(offset / 60));
    const minutes = Math.abs(offset % 60);
    const sign = offset <= 0 ? "+" : "-";
    return `(GMT${sign}${hours}:${minutes.toString().padStart(2, "0")})`;
  }, []);

  // DatePicker theme configuration
  const datePickerTheme = {
    token: {
      colorPrimary: "#965CDE",
      colorPrimaryHover: "#a873e5",
      colorPrimaryActive: "#8348c7",
    },
    components: {
      DatePicker: {
        colorBgContainer: "#1A1A1A",
        colorBorder: "#3a3a3a",
        colorText: "#EEEEEE",
        colorTextPlaceholder: "#666666",
        colorBgElevated: "#1A1A1A",
        colorPrimary: "#965CDE",
        colorPrimaryBg: "#2A1F3D",
        colorPrimaryBgHover: "#3A2F4D",
        colorTextLightSolid: "#FFFFFF",
        controlItemBgActive: "#965CDE",
        colorLink: "#965CDE",
        colorLinkHover: "#a873e5",
        colorLinkActive: "#8348c7",
        cellActiveWithRangeBg: "#2A1F3D",
        cellHoverBg: "#2a2a2a",
        cellRangeBorderColor: "#965CDE",
      },
    },
  };

  // Popover content
  const popoverContent = (
    <div className="w-[580px] bg-[#1A1A1A] rounded-lg overflow-hidden">
      {/* Tab Header */}
      <div className="flex border-b border-[#3a3a3a]">
        <button
          className={`flex-1 py-3 px-4 text-center transition-colors ${
            activeTab === "preset"
              ? "bg-[#2a2a2a] text-white"
              : "text-[#B3B3B3] hover:text-white hover:bg-[#222222]"
          }`}
          onClick={() => setActiveTab("preset")}
        >
          <Text_12_600_EEEEEE
            className={activeTab === "preset" ? "" : "!text-[#B3B3B3]"}
          >
            Time from now
          </Text_12_600_EEEEEE>
        </button>
        <button
          className={`flex-1 py-3 px-4 text-center transition-colors ${
            activeTab === "custom"
              ? "bg-[#2a2a2a] text-white"
              : "text-[#B3B3B3] hover:text-white hover:bg-[#222222]"
          }`}
          onClick={() => setActiveTab("custom")}
        >
          <Text_12_600_EEEEEE
            className={activeTab === "custom" ? "" : "!text-[#B3B3B3]"}
          >
            Custom range
          </Text_12_600_EEEEEE>
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === "preset" ? (
        // Preset List
        <div className="py-2">
          {PRESET_OPTIONS.map((preset) => (
            <button
              key={preset.value}
              className={`w-full text-left px-4 py-2 transition-colors ${
                selectedPreset === preset.value && !isCustom
                  ? "bg-[#2A1F3D] text-white"
                  : "text-[#B3B3B3] hover:bg-[#222222] hover:text-white"
              }`}
              onClick={() => handlePresetSelect(preset)}
            >
              <Text_12_400_EEEEEE
                className={
                  selectedPreset === preset.value && !isCustom
                    ? ""
                    : "!text-[#B3B3B3]"
                }
              >
                {preset.label}
              </Text_12_400_EEEEEE>
            </button>
          ))}
        </div>
      ) : (
        // Custom Range
        <div className="p-4">
          {/* Timezone Display */}
          <div className="flex items-center justify-between mb-4">
            <Text_12_400_757575>{timezone} Local timezone</Text_12_400_757575>
          </div>

          {/* Date Inputs Display */}
          <div className="flex gap-4 mb-4">
            {/* Start Date */}
            <div className="flex-1">
              <Text_10_400_B3B3B3 className="block mb-1">Start date</Text_10_400_B3B3B3>
              <div className="bg-[#0d0d0d] border border-[#3a3a3a] rounded px-3 py-2">
                <Text_12_400_EEEEEE>
                  {customRange
                    ? customRange[0].format("YYYY / MM / DD , HH : mm : ss")
                    : "Select start date"}
                </Text_12_400_EEEEEE>
              </div>
              <Text_10_400_B3B3B3 className="block mt-1">YYYY/MM/DD</Text_10_400_B3B3B3>
            </div>

            {/* End Date */}
            <div className="flex-1">
              <Text_10_400_B3B3B3 className="block mb-1">End date</Text_10_400_B3B3B3>
              <div className="bg-[#0d0d0d] border border-[#3a3a3a] rounded px-3 py-2">
                <Text_12_400_EEEEEE>
                  {customRange
                    ? customRange[1].format("YYYY / MM / DD , HH : mm : ss")
                    : "Select end date"}
                </Text_12_400_EEEEEE>
              </div>
              <Text_10_400_B3B3B3 className="block mt-1">YYYY/MM/DD</Text_10_400_B3B3B3>
            </div>
          </div>

          {/* Range Picker Calendar */}
          <ConfigProvider theme={datePickerTheme}>
            <RangePicker
              value={customRange}
              onChange={handleCustomRangeChange}
              showTime={{ format: "HH:mm:ss" }}
              format="YYYY-MM-DD HH:mm:ss"
              className="w-full bg-[#0d0d0d] border-[#3a3a3a] hover:border-[#965CDE]"
              popupClassName="logfire-range-picker-popup"
              open
              getPopupContainer={(trigger) => trigger.parentElement || document.body}
              style={{ visibility: "hidden", height: 0, padding: 0, border: "none" }}
              panelRender={(panelNode) => (
                <div className="bg-[#1A1A1A]">{panelNode}</div>
              )}
            />
          </ConfigProvider>

          {/* Inline Calendar Display */}
          <div className="mt-4">
            <ConfigProvider theme={datePickerTheme}>
              <RangePicker
                value={customRange}
                onChange={handleCustomRangeChange}
                showTime={{ format: "HH:mm:ss" }}
                format="YYYY-MM-DD HH:mm:ss"
                className="w-full bg-[#0d0d0d] border-[#3a3a3a] hover:border-[#965CDE]"
                placeholder={["Start Date", "End Date"]}
              />
            </ConfigProvider>
          </div>

          {/* Select Button */}
          <button
            className="w-full mt-4 py-3 bg-[#965CDE] hover:bg-[#a873e5] text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={handleSelectCustomRange}
            disabled={!customRange}
          >
            Select
          </button>
        </div>
      )}
    </div>
  );

  return (
    <Popover
      content={popoverContent}
      trigger="click"
      open={open}
      onOpenChange={setOpen}
      placement="bottomRight"
      arrow={false}
      overlayClassName="logfire-date-picker-popover"
      overlayInnerStyle={{
        padding: 0,
        background: "#1A1A1A",
        border: "1px solid #3a3a3a",
        borderRadius: "8px",
      }}
    >
      <button
        className={`flex items-center gap-2 px-3 py-1.5 bg-[#1A1A1A] border border-[#3a3a3a] rounded-md hover:border-[#965CDE] transition-colors ${className}`}
      >
        <Calendar className="w-4 h-4 text-[#B3B3B3]" />
        <Text_12_400_EEEEEE className="whitespace-nowrap">
          {displayText}
        </Text_12_400_EEEEEE>
        <ChevronDown className="w-4 h-4 text-[#B3B3B3]" />
      </button>
    </Popover>
  );
};

export default LogfireDateRangePicker;

// Export preset options for use in parent components
export { PRESET_OPTIONS, PRESET_LABEL_MAP };
