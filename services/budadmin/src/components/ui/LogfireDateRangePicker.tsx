import React, { useState, useEffect, useMemo } from "react";
import { DatePicker, ConfigProvider, Popover, Input } from "antd";
import { Calendar, ChevronDown } from "lucide-react";
import dayjs from "dayjs";
import type { Dayjs } from "dayjs";
import {
  Text_10_400_B3B3B3,
  Text_12_400_757575,
  Text_12_400_EEEEEE,
  Text_12_600_EEEEEE,
} from "@/components/ui/text";
import { PrimaryButton } from "./bud/form/Buttons";

const { RangePicker } = DatePicker;

// Preset time range options matching Logfire
interface PresetOption {
  label: string;
  value: string;
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

const PRESET_LABEL_MAP: Record<string, string> = PRESET_OPTIONS.reduce(
  (acc, opt) => {
    acc[opt.value] = opt.label;
    return acc;
  },
  {} as Record<string, string>
);

export interface DateRangeValue {
  preset?: string;
  startDate?: Dayjs;
  endDate?: Dayjs;
}

export interface LogfireDateRangePickerProps {
  value?: DateRangeValue;
  onChange?: (value: DateRangeValue) => void;
  presetValue?: string;
  onPresetChange?: (preset: string) => void;
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

  const [selectedPreset, setSelectedPreset] = useState<string>(
    presetValue || value?.preset || "5m"
  );
  const [customRange, setCustomRange] = useState<[Dayjs, Dayjs] | null>(
    value?.startDate && value?.endDate
      ? [value.startDate, value.endDate]
      : null
  );

  // Separate state for date and time inputs (for manual editing)
  const [startDateStr, setStartDateStr] = useState("");
  const [startTimeStr, setStartTimeStr] = useState("00:00:00");
  const [endDateStr, setEndDateStr] = useState("");
  const [endTimeStr, setEndTimeStr] = useState("00:00:00");

  const [isCustom, setIsCustom] = useState(
    !!(value?.startDate && value?.endDate && !value?.preset)
  );

  // Sync input strings when customRange changes
  useEffect(() => {
    if (customRange) {
      setStartDateStr(customRange[0].format("YYYY/MM/DD"));
      setStartTimeStr(customRange[0].format("HH:mm:ss"));
      setEndDateStr(customRange[1].format("YYYY/MM/DD"));
      setEndTimeStr(customRange[1].format("HH:mm:ss"));
    }
  }, [customRange]);

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

  const displayText = useMemo(() => {
    if (isCustom && customRange) {
      const [start, end] = customRange;
      return `${start.format("MMM D, HH:mm")} - ${end.format("MMM D, HH:mm")}`;
    }
    return PRESET_LABEL_MAP[selectedPreset] || "Last 5 minutes";
  }, [isCustom, customRange, selectedPreset]);

  const handlePresetSelect = (preset: PresetOption) => {
    setSelectedPreset(preset.value);
    setIsCustom(false);
    setOpen(false);

    if (onPresetChange) {
      onPresetChange(preset.value);
    }
    if (onChange) {
      onChange({ preset: preset.value });
    }
  };

  // Handle calendar date range selection - sets time to 00:00:00 for start and 23:59:59 for end
  const handleCalendarChange = (
    dates: [Dayjs | null, Dayjs | null] | null
  ) => {
    if (dates && dates[0] && dates[1]) {
      // Preserve existing time if already set, otherwise use defaults
      const startTime = startTimeStr || "00:00:00";
      const endTime = endTimeStr || "23:59:59";

      const [sh, sm, ss] = startTime.split(":").map(Number);
      const [eh, em, es] = endTime.split(":").map(Number);

      const newStart = dates[0].hour(sh || 0).minute(sm || 0).second(ss || 0);
      const newEnd = dates[1].hour(eh || 23).minute(em || 59).second(es || 59);

      setCustomRange([newStart, newEnd]);
    }
  };

  // Handle manual date input change
  const handleStartDateInput = (value: string) => {
    setStartDateStr(value);
    const parsed = dayjs(value, "YYYY/MM/DD", true);
    if (parsed.isValid()) {
      const [h, m, s] = startTimeStr.split(":").map(Number);
      const newStart = parsed.hour(h || 0).minute(m || 0).second(s || 0);
      if (customRange) {
        setCustomRange([newStart, customRange[1]]);
      } else {
        setCustomRange([newStart, dayjs().endOf("day")]);
      }
    }
  };

  const handleEndDateInput = (value: string) => {
    setEndDateStr(value);
    const parsed = dayjs(value, "YYYY/MM/DD", true);
    if (parsed.isValid()) {
      const [h, m, s] = endTimeStr.split(":").map(Number);
      const newEnd = parsed.hour(h || 23).minute(m || 59).second(s || 59);
      if (customRange) {
        setCustomRange([customRange[0], newEnd]);
      } else {
        setCustomRange([dayjs().startOf("day"), newEnd]);
      }
    }
  };

  // Handle manual time input change
  const handleStartTimeInput = (value: string) => {
    setStartTimeStr(value);
    const timeRegex = /^(\d{1,2}):(\d{1,2}):(\d{1,2})$/;
    const match = value.match(timeRegex);
    if (match && customRange) {
      const [, h, m, s] = match.map(Number);
      if (h <= 23 && m <= 59 && s <= 59) {
        const newStart = customRange[0].hour(h).minute(m).second(s);
        setCustomRange([newStart, customRange[1]]);
      }
    }
  };

  const handleEndTimeInput = (value: string) => {
    setEndTimeStr(value);
    const timeRegex = /^(\d{1,2}):(\d{1,2}):(\d{1,2})$/;
    const match = value.match(timeRegex);
    if (match && customRange) {
      const [, h, m, s] = match.map(Number);
      if (h <= 23 && m <= 59 && s <= 59) {
        const newEnd = customRange[1].hour(h).minute(m).second(s);
        setCustomRange([customRange[0], newEnd]);
      }
    }
  };

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

  const timezone = useMemo(() => {
    const offset = new Date().getTimezoneOffset();
    const hours = Math.abs(Math.floor(offset / 60));
    const minutes = Math.abs(offset % 60);
    const sign = offset <= 0 ? "+" : "-";
    return `(GMT${sign}${hours}:${minutes.toString().padStart(2, "0")})`;
  }, []);

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
      Input: {
        colorBgContainer: "#0d0d0d",
        colorBorder: "#3a3a3a",
        colorText: "#EEEEEE",
        colorTextPlaceholder: "#666666",
      },
    },
  };

  const popoverContent = (
    <div className="w-[600px] bg-[#1A1A1A] rounded-lg overflow-hidden">
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
        <div className="p-4">
          {/* Timezone Display */}
          <div className="flex items-center justify-between mb-3">
            <Text_12_400_757575>{timezone} Local timezone</Text_12_400_757575>
          </div>

          <ConfigProvider theme={datePickerTheme}>
            {/* Date Range Picker - at top for visibility */}
            <RangePicker
              value={customRange}
              onChange={handleCalendarChange}
              format="YYYY-MM-DD"
              className="w-full bg-[#0d0d0d] border-[#3a3a3a] hover:border-[#965CDE] mb-4"
              placeholder={["Select start date", "Select end date"]}
              getPopupContainer={() => document.body}
              allowClear={false}
              popupClassName="logfire-range-picker-popup"
            />

            {/* Editable Date/Time Inputs - below calendar for fine-tuning */}
            <div className="flex gap-4 mb-4">
              {/* Start Date/Time */}
              <div className="flex-1">
                <Text_10_400_B3B3B3 className="block mb-1">Start date & time</Text_10_400_B3B3B3>
                <div className="flex gap-2">
                  <Input
                    value={startDateStr}
                    onChange={(e) => handleStartDateInput(e.target.value)}
                    placeholder="YYYY/MM/DD"
                    className="flex-1 bg-[#0d0d0d] border-[#3a3a3a] text-[#EEEEEE] text-xs"
                  />
                  <Input
                    value={startTimeStr}
                    onChange={(e) => handleStartTimeInput(e.target.value)}
                    placeholder="HH:mm:ss"
                    className="w-20 bg-[#0d0d0d] border-[#3a3a3a] text-[#EEEEEE] text-xs"
                  />
                </div>
              </div>

              {/* End Date/Time */}
              <div className="flex-1">
                <Text_10_400_B3B3B3 className="block mb-1">End date & time</Text_10_400_B3B3B3>
                <div className="flex gap-2">
                  <Input
                    value={endDateStr}
                    onChange={(e) => handleEndDateInput(e.target.value)}
                    placeholder="YYYY/MM/DD"
                    className="flex-1 bg-[#0d0d0d] border-[#3a3a3a] text-[#EEEEEE] text-xs"
                  />
                  <Input
                    value={endTimeStr}
                    onChange={(e) => handleEndTimeInput(e.target.value)}
                    placeholder="HH:mm:ss"
                    className="w-20 bg-[#0d0d0d] border-[#3a3a3a] text-[#EEEEEE] text-xs"
                  />
                </div>
              </div>
            </div>
          </ConfigProvider>

          {/* Select Button */}
          <div className="flex justify-end">
            <PrimaryButton
            className="w-full"
            onClick={handleSelectCustomRange}
            disabled={!customRange}
          >
            Select
          </PrimaryButton>
          </div>
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
      styles={{
        body: {
          padding: 0,
          background: "#1A1A1A",
          border: "1px solid #3a3a3a",
          borderRadius: "8px",
        },
      }}
    >
      <button
        className={`flex items-center gap-2 px-3 py-[.25rem] bg-[#1A1A1A] border border-[#3a3a3a] rounded-md hover:border-[#965CDE] transition-colors ${className}`}
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

export { PRESET_OPTIONS, PRESET_LABEL_MAP };
