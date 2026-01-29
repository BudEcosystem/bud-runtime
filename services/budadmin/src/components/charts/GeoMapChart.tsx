import React, { useEffect, useRef, useState } from "react";
import * as echarts from "echarts";
import { Text_12_400_B3B3B3, Text_12_500_FFFFFF } from "@/components/ui/text";
import { GlobalOutlined, LoadingOutlined } from "@ant-design/icons";

export interface GeographicDataPoint {
  location_key: string;
  country_code: string;
  country_name: string;
  region?: string;
  city?: string;
  latitude?: number;
  longitude?: number;
  request_count: number;
  success_rate: number;
  avg_latency_ms: number;
  percentage: number;
}

interface GeoMapChartProps {
  data?: GeographicDataPoint[];
  isLoading?: boolean;
}

// Country coordinates for fallback when lat/long not provided
const COUNTRY_COORDINATES: { [key: string]: [number, number] } = {
  US: [-95.7129, 37.0902],
  USA: [-95.7129, 37.0902],
  GB: [-3.436, 55.3781],
  UK: [-3.436, 55.3781],
  DE: [10.4515, 51.1657],
  FR: [2.2137, 46.2276],
  JP: [138.2529, 36.2048],
  CN: [104.1954, 35.8617],
  IN: [78.9629, 20.5937],
  BR: [-51.9253, -14.235],
  CA: [-106.3468, 56.1304],
  AU: [133.7751, -25.2744],
  IT: [12.5674, 41.8719],
  ES: [-3.7492, 40.4637],
  NL: [5.2913, 52.1326],
  KR: [127.7669, 35.9078],
  MX: [-102.5528, 23.6345],
  RU: [105.3188, 61.524],
  SG: [103.8198, 1.3521],
  SE: [18.6435, 60.1282],
  NO: [8.4689, 60.472],
  DK: [9.5018, 56.2639],
  FI: [25.7482, 61.9241],
  CH: [8.2275, 46.8182],
  AT: [14.5501, 47.5162],
  BE: [4.4699, 50.5039],
  IE: [-8.2439, 53.4129],
  PL: [19.1451, 51.9194],
  PT: [-8.2245, 39.3999],
  GR: [21.8243, 39.0742],
  CZ: [15.473, 49.8175],
  HU: [19.5033, 47.1625],
  RO: [24.9668, 45.9432],
  IL: [34.8516, 31.0461],
  AE: [53.8478, 23.4241],
  SA: [45.0792, 23.8859],
  ZA: [22.9375, -30.5595],
  EG: [30.8025, 26.8206],
  NG: [8.6753, 9.082],
  KE: [37.9062, -0.0236],
  AR: [-63.6167, -38.4161],
  CL: [-71.543, -35.6751],
  CO: [-74.2973, 4.5709],
  PE: [-75.0152, -9.19],
  VE: [-66.5897, 6.4238],
  NZ: [174.886, -40.9006],
  TH: [100.9925, 15.87],
  MY: [101.9758, 4.2105],
  ID: [113.9213, -0.7893],
  PH: [121.774, 12.8797],
  VN: [108.2772, 14.0583],
  PK: [69.3451, 30.3753],
  BD: [90.3563, 23.685],
  TR: [35.2433, 38.9637],
  IR: [53.688, 32.4279],
  IQ: [43.6793, 33.2232],
  UA: [31.1656, 48.3794],
  BY: [27.9534, 53.7098],
  KZ: [66.9237, 48.0196],
};

const GeoMapChart: React.FC<GeoMapChartProps> = ({
  data = [],
  isLoading = false,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [mapLoadError, setMapLoadError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const [containerHeight, setContainerHeight] = useState("25rem");
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);

  // Helper function to extract array data from different possible structures
  const extractArrayData = (inputData: any): GeographicDataPoint[] => {
    if (Array.isArray(inputData)) {
      return inputData;
    } else if (inputData && typeof inputData === "object") {
      if (Array.isArray(inputData.locations)) {
        return inputData.locations;
      } else if (Array.isArray(inputData.data)) {
        return inputData.data;
      } else if (Array.isArray(inputData.items)) {
        return inputData.items;
      }
    }
    return [];
  };

  // Function to get coordinates for a location
  const getCoordinates = (
    point: GeographicDataPoint,
  ): [number, number] | null => {
    // Use provided coordinates if available
    if (
      point.latitude !== undefined &&
      point.longitude !== undefined &&
      point.latitude !== 0 &&
      point.longitude !== 0
    ) {
      return [point.longitude, point.latitude];
    }

    // Fallback to country coordinates
    const countryCode = point.country_code?.toUpperCase();
    if (countryCode && COUNTRY_COORDINATES[countryCode]) {
      // Add some random offset for cities within the same country
      const baseCoords = COUNTRY_COORDINATES[countryCode];
      const offset = point.city
        ? [(Math.random() - 0.5) * 5, (Math.random() - 0.5) * 5]
        : [0, 0];
      return [baseCoords[0] + offset[0], baseCoords[1] + offset[1]];
    }

    return null;
  };

  // Load world map with retry logic
  const loadWorldMap = async (attempt = 0) => {
    const maxAttempts = 3;

    try {
      // Use India-compliant world map with correct Kashmir boundaries
      const response = await fetch("/maps/world-india-compliant.json");
      if (!response.ok) throw new Error("Failed to fetch map data");

      const worldJson = await response.json();
      echarts.registerMap("world", worldJson);
      setMapLoaded(true);
      setMapLoadError(false);
      return true;
    } catch (error) {
      console.error(
        `Failed to load world map (attempt ${attempt + 1}):`,
        error,
      );

      if (attempt < maxAttempts - 1) {
        // Retry with exponential backoff
        await new Promise((resolve) =>
          setTimeout(resolve, Math.pow(2, attempt) * 1000),
        );
        return loadWorldMap(attempt + 1);
      } else {
        setMapLoadError(true);
        return false;
      }
    }
  };

  // Initialize chart
  useEffect(() => {
    if (!chartRef.current) return;

    // Initialize ECharts instance if not already created
    if (!chartInstanceRef.current) {
      chartInstanceRef.current = echarts.init(chartRef.current, "dark");
    }

    const chart = chartInstanceRef.current;

    // Load map if not loaded
    if (!mapLoaded && !mapLoadError) {
      loadWorldMap().then((success) => {
        if (success) {
          renderChart();
        }
      });
    } else if (mapLoaded) {
      renderChart();
    }

    function renderChart() {
      // Extract array data from different possible structures
      const arrayData = extractArrayData(data);

      // Process data and filter out invalid coordinates
      const validData = arrayData
        .map((item) => {
          const coords = getCoordinates(item);
          if (!coords) return null;

          return {
            name: item.city || item.country_name,
            value: [
              coords[0],
              coords[1],
              item.request_count,
              item.success_rate,
              item.avg_latency_ms,
              item.percentage,
            ],
            country_code: item.country_code,
            country_name: item.country_name,
            city: item.city,
            region: item.region,
            request_count: item.request_count,
            success_rate: item.success_rate,
            avg_latency_ms: item.avg_latency_ms,
            percentage: item.percentage,
          };
        })
        .filter((item) => item !== null);

      // Only use sample data if we explicitly have no data passed (not just empty array)
      const displayData =
        validData.length > 0
          ? validData
          : data === undefined || data === null
            ? getSampleData()
            : [];

      // Calculate max values for scaling
      const maxRequests = Math.max(...displayData.map((d) => d.value[2]), 1);
      const maxLatency = Math.max(...displayData.map((d) => d.value[4]), 1);

      // Create country highlighting data
      const countryHighlights = createCountryHighlights(arrayData);

      // If no data, show empty message on map
      if (displayData.length === 0) {
        const emptyOption: echarts.EChartsOption = {
          backgroundColor: "transparent",
          title: {
            show: true,
            text: "No Geographic Data",
            subtext: "No requests in selected time range",
            left: "center",
            top: "center",
            textStyle: { color: "#757575", fontSize: 16 },
            subtextStyle: { color: "#505050", fontSize: 14 },
          },
          geo: {
            map: "world",
            roam: false,
            silent: true,
            itemStyle: {
              areaColor: "#1a1a1a",
              borderColor: "#2a2a2a",
              borderWidth: 0.5,
            },
          },
        };
        chart.setOption(emptyOption);
        return;
      }

      const option: echarts.EChartsOption = {
        backgroundColor: "transparent",
        title: {
          show: false,
        },
        tooltip: {
          trigger: "item",
          formatter: function (params: any) {
            if (params.value && params.data) {
              const data = params.data;
              const location = data.city
                ? `${data.city}, ${data.country_name}`
                : data.country_name;

              return `
                <div style="padding: 10px; min-width: 200px;">
                  <div style="font-weight: bold; margin-bottom: 8px; color: #FFFFFF;">
                    ${location}
                  </div>
                  <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span style="color: #B3B3B3;">Requests:</span>
                    <span style="color: #3F8EF7; font-weight: 500;">
                      ${data.request_count.toLocaleString()} (${data.percentage.toFixed(1)}%)
                    </span>
                  </div>
                  <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span style="color: #B3B3B3;">Success Rate:</span>
                    <span style="color: ${data.success_rate >= 95 ? "#22c55e" : "#f59e0b"}; font-weight: 500;">
                      ${data.success_rate.toFixed(1)}%
                    </span>
                  </div>
                  <div style="display: flex; justify-content: space-between;">
                    <span style="color: #B3B3B3;">Avg Latency:</span>
                    <span style="color: #FFC442; font-weight: 500;">
                      ${Math.round(data.avg_latency_ms)}ms
                    </span>
                  </div>
                </div>
              `;
            }
            return params.name;
          },
          backgroundColor: "rgba(26, 26, 26, 0.95)",
          borderColor: "#333",
          borderWidth: 1,
          textStyle: {
            color: "#EEEEEE",
            fontSize: 12,
          },
        },
        visualMap: {
          show: true,
          type: "continuous",
          min: 0,
          max: maxRequests,
          text: ["High", "Low"],
          realtime: false,
          calculable: true,
          inRange: {
            color: [
              "#dec4ff",
              "#ccaafc",
              "#ba90f2",
              "#a876e8",
              "#965CDE",
              "#824fa0",
              "#6a4287",
              "#53356f",
              "#3d2857",
              "#2a1a3e",
            ],
          },
          textStyle: {
            color: "#B3B3B3",
            fontSize: 10,
          },
          itemWidth: 15,
          itemHeight: 100,
          left: 10,
          bottom: 20,
        },
        geo: {
          map: "world",
          roam: true,
          zoom: 1.2,
          center: [0, 10],
          scaleLimit: {
            min: 0.8,
            max: 5,
          },
          itemStyle: {
            areaColor: "#1a1a1a",
            borderColor: "#2a2a2a",
            borderWidth: 0.5,
          },
          emphasis: {
            itemStyle: {
              areaColor: "#4a3a5a",
              borderColor: "#965CDE",
              borderWidth: 2,
              shadowBlur: 10,
              shadowColor: "rgba(150, 92, 222, 0.3)",
            },
            label: {
              show: true,
              color: "#FFFFFF",
            },
          },
          regions: countryHighlights,
          label: {
            show: false,
          },
        },
        series: [
          // Scatter series for exact locations with ripple effect
          {
            name: "Locations",
            type: "effectScatter",
            coordinateSystem: "geo",
            data: displayData,
            symbolSize: function (val: number[]) {
              // Size based on request count
              const size = Math.sqrt(val[2] / maxRequests) * 30;
              return Math.max(8, Math.min(size, 40));
            },
            showEffectOn: "render",
            rippleEffect: {
              brushType: "stroke",
              scale: 2.5,
              period: 4,
              color: "#965CDE",
            },
            itemStyle: {
              color: function (params: any) {
                // Use purple gradient based on request count - darker for higher values
                const value = params.value[2];
                const ratio = value / maxRequests;
                // Interpolate between light and dark purple (reversed)
                if (ratio < 0.2) return "#ccaafc"; // Light purple for low values
                if (ratio < 0.4) return "#ba90f2";
                if (ratio < 0.6) return "#a876e8";
                if (ratio < 0.8) return "#965CDE";
                return "#824fa0"; // Dark purple for high values
              },
              borderColor: "#965CDE",
              borderWidth: 1,
              shadowBlur: 10,
              shadowColor: "rgba(150, 92, 222, 0.5)",
            },
            emphasis: {
              scale: 1.5,
              itemStyle: {
                color: "#ba90f2",
                borderColor: "#FFFFFF",
                borderWidth: 2,
                shadowBlur: 20,
                shadowColor: "rgba(186, 144, 242, 0.8)",
              },
            },
            zlevel: 2,
          },
          // Additional scatter layer for purple glow effect
          {
            name: "Glow",
            type: "scatter",
            coordinateSystem: "geo",
            data: displayData,
            symbolSize: function (val: number[]) {
              // Larger size for glow effect
              const size = Math.sqrt(val[2] / maxRequests) * 45;
              return Math.max(12, Math.min(size, 60));
            },
            itemStyle: {
              color: "rgba(150, 92, 222, 0.2)",
              opacity: 0.4,
              shadowBlur: 30,
              shadowColor: "rgba(150, 92, 222, 0.3)",
            },
            silent: true,
            zlevel: 1,
          },
        ],
        // Add zoom control buttons
        toolbox: {
          show: true,
          orient: "vertical",
          right: 10,
          top: 10,
          feature: {
            restore: {
              show: true,
              title: "Reset",
            },
            saveAsImage: {
              show: true,
              title: "Save",
              pixelRatio: 2,
            },
          },
          iconStyle: {
            borderColor: "#757575",
          },
          emphasis: {
            iconStyle: {
              borderColor: "#FFFFFF",
            },
          },
        },
        grid: {
          containLabel: true,
          left: 0,
          right: 0,
          top: 0,
          bottom: 0,
        },
      };

      chart.setOption(option);

      // Handle zoom events to adjust container height
      chart.on("georoam", function (params: any) {
        setTimeout(() => {
          if (chartRef.current && chartInstanceRef.current) {
            const currentOption = chartInstanceRef.current.getOption();
            const geoComponent = currentOption.geo?.[0];
            const zoom = geoComponent?.zoom || 1.2;

            // Calculate dynamic height based on zoom level
            // Base height is 25rem for zoom level 1.2 (our initial zoom)
            const baseHeight = 25;
            const minHeight = 25;
            const maxHeight = 35; // Reduced max height

            // More conservative scaling formula
            // At zoom 0.8 = 25rem
            // At zoom 1.2 (initial) = 25rem
            // At zoom 2 = ~27rem
            // At zoom 3 = ~30rem
            // At zoom 5 = 35rem

            // Only increase height if zoom is greater than initial
            let newHeight = minHeight;
            if (zoom > 1.2) {
              // Linear scaling with gentler slope
              let scaleFactor = (zoom - 1.2) * 3;
              newHeight = Math.min(maxHeight, minHeight + scaleFactor);
            }

            // Apply smooth transition
            setContainerHeight(`${newHeight}rem`);
          }
        }, 50); // Small delay to ensure the zoom value is updated
      });

      // Handle restore (reset) specifically
      chart.on("restore", function () {
        // Reset to initial height when restore is clicked
        setContainerHeight("25rem");
      });
    }

    const handleResize = () => {
      chart.resize();
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      // Clean up event listeners
      if (chartInstanceRef.current) {
        chartInstanceRef.current.off("georoam");
        chartInstanceRef.current.off("restore");
      }
    };
  }, [data, mapLoaded, mapLoadError]);

  // Resize chart when container height changes
  useEffect(() => {
    if (chartInstanceRef.current) {
      // Small delay to ensure DOM has updated
      setTimeout(() => {
        chartInstanceRef.current?.resize();
      }, 100);
    }
  }, [containerHeight]);

  // Function to get color based on metrics (kept for potential future use)
  // const getColorByMetric = (successRate: number, latency: number): string => {
  //   // Color based on success rate and latency
  //   if (successRate >= 98 && latency < 100) return '#22c55e'; // Excellent
  //   if (successRate >= 95 && latency < 500) return '#3F8EF7'; // Good
  //   if (successRate >= 90 && latency < 1000) return '#FFC442'; // Fair
  //   if (successRate >= 85) return '#f59e0b'; // Warning
  //   return '#ef4444'; // Poor
  // };

  // Function to create country highlighting regions with purple theme
  const createCountryHighlights = (data: GeographicDataPoint[]) => {
    const countryData: {
      [key: string]: { requests: number; successRate: number };
    } = {};

    data.forEach((item) => {
      const country = item.country_name;
      if (!country) return;

      if (!countryData[country]) {
        countryData[country] = { requests: 0, successRate: 0 };
      }
      countryData[country].requests += item.request_count;
      // Average success rate (simplified)
      countryData[country].successRate =
        (countryData[country].successRate + item.success_rate) / 2;
    });

    return Object.entries(countryData).map(([country, data]) => ({
      name: country,
      itemStyle: {
        // Use darker purple for higher request counts
        areaColor: `rgba(106, 66, 135, ${Math.min(data.requests / 1000, 0.4)})`, // Darker purple base
        borderColor: "#7c4daa",
        borderWidth: 0.5,
      },
      emphasis: {
        itemStyle: {
          areaColor: `rgba(130, 79, 160, 0.7)`, // Darker purple on hover
          borderColor: "#965CDE",
          borderWidth: 2,
          shadowBlur: 15,
          shadowColor: "rgba(150, 92, 222, 0.5)",
        },
      },
    }));
  };

  // Get sample data for demonstration
  const getSampleData = () => [
    {
      name: "New York, USA",
      value: [-74.006, 40.7128, 450, 98.5, 120, 25.2],
      country_code: "US",
      country_name: "United States",
      city: "New York",
      request_count: 450,
      success_rate: 98.5,
      avg_latency_ms: 120,
      percentage: 25.2,
    },
    {
      name: "London, UK",
      value: [-0.1276, 51.5074, 280, 97.2, 95, 15.7],
      country_code: "GB",
      country_name: "United Kingdom",
      city: "London",
      request_count: 280,
      success_rate: 97.2,
      avg_latency_ms: 95,
      percentage: 15.7,
    },
    {
      name: "Berlin, Germany",
      value: [13.405, 52.52, 220, 99.1, 85, 12.3],
      country_code: "DE",
      country_name: "Germany",
      city: "Berlin",
      request_count: 220,
      success_rate: 99.1,
      avg_latency_ms: 85,
      percentage: 12.3,
    },
    {
      name: "Tokyo, Japan",
      value: [139.6503, 35.6762, 180, 96.8, 110, 10.1],
      country_code: "JP",
      country_name: "Japan",
      city: "Tokyo",
      request_count: 180,
      success_rate: 96.8,
      avg_latency_ms: 110,
      percentage: 10.1,
    },
    {
      name: "Toronto, Canada",
      value: [-79.3832, 43.6532, 150, 98.9, 105, 8.4],
      country_code: "CA",
      country_name: "Canada",
      city: "Toronto",
      request_count: 150,
      success_rate: 98.9,
      avg_latency_ms: 105,
      percentage: 8.4,
    },
    {
      name: "Sydney, Australia",
      value: [151.2093, -33.8688, 120, 97.5, 140, 6.7],
      country_code: "AU",
      country_name: "Australia",
      city: "Sydney",
      request_count: 120,
      success_rate: 97.5,
      avg_latency_ms: 140,
      percentage: 6.7,
    },
    {
      name: "Singapore",
      value: [103.8198, 1.3521, 100, 99.2, 75, 5.6],
      country_code: "SG",
      country_name: "Singapore",
      city: "Singapore",
      request_count: 100,
      success_rate: 99.2,
      avg_latency_ms: 75,
      percentage: 5.6,
    },
    {
      name: "São Paulo, Brazil",
      value: [-46.6333, -23.5505, 90, 95.8, 160, 5.0],
      country_code: "BR",
      country_name: "Brazil",
      city: "São Paulo",
      request_count: 90,
      success_rate: 95.8,
      avg_latency_ms: 160,
      percentage: 5.0,
    },
  ];

  if (isLoading) {
    return (
      <div
        className="flex flex-col items-center justify-center gap-3 transition-all duration-300"
        style={{ height: containerHeight }}
      >
        <LoadingOutlined style={{ fontSize: 32, color: "#3F8EF7" }} spin />
        <Text_12_400_B3B3B3>Loading geographic data...</Text_12_400_B3B3B3>
      </div>
    );
  }

  if (mapLoadError && retryCount >= 3) {
    return (
      <div
        className="flex flex-col items-center justify-center gap-3 transition-all duration-300"
        style={{ height: containerHeight }}
      >
        <GlobalOutlined style={{ fontSize: 48, color: "#757575" }} />
        <Text_12_500_FFFFFF>
          Unable to load map visualization
        </Text_12_500_FFFFFF>
        <Text_12_400_B3B3B3 className="text-center max-w-md">
          The geographic map could not be loaded. Please check your internet
          connection and try refreshing the page.
        </Text_12_400_B3B3B3>
        <button
          onClick={() => {
            setRetryCount(0);
            setMapLoadError(false);
            loadWorldMap();
          }}
          className="mt-2 px-4 py-2 bg-[#3F8EF7] text-white rounded hover:bg-[#5FA5F7] transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  // Check if we have any geographic data
  const arrayData = extractArrayData(data);

  // Show empty state if data is explicitly empty array
  if (data !== undefined && data !== null && arrayData.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center gap-3"
        style={{ height: "25rem" }}
      >
        <GlobalOutlined style={{ fontSize: 48, color: "#757575" }} />
        <Text_12_500_FFFFFF>No geographic data available</Text_12_500_FFFFFF>
        <Text_12_400_B3B3B3 className="text-center max-w-md">
          No requests found in the selected time range. Try adjusting the time
          period or filters.
        </Text_12_400_B3B3B3>
      </div>
    );
  }

  // Render the chart container - will show sample data only if data is undefined/null
  return (
    <div
      className="transition-all duration-300"
      style={{ position: "relative", width: "100%", height: containerHeight }}
    >
      <div ref={chartRef} style={{ width: "100%", height: "100%" }} />
      {!mapLoaded && !mapLoadError && (
        <div className="absolute inset-0 flex items-center justify-center bg-[#101010] bg-opacity-90 pointer-events-none">
          <div className="flex flex-col items-center gap-3">
            <LoadingOutlined style={{ fontSize: 32, color: "#3F8EF7" }} spin />
            <Text_12_400_B3B3B3>Loading world map...</Text_12_400_B3B3B3>
          </div>
        </div>
      )}
      {(data === undefined || data === null) && mapLoaded && (
        <div className="absolute top-4 left-4 flex flex-col gap-1 pointer-events-none">
          <Text_12_500_FFFFFF className="opacity-80">
            Geographic Distribution
          </Text_12_500_FFFFFF>
          <Text_12_400_B3B3B3 className="text-xs opacity-60">
            Sample data shown for demonstration
          </Text_12_400_B3B3B3>
        </div>
      )}
    </div>
  );
};

export default GeoMapChart;
