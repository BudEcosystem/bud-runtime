#!/bin/bash
# NFD Local Hook for CPU Model Detection
# This script extracts detailed CPU information that NFD's cpu source might miss

# Function to get CPU model from various sources
get_cpu_model() {
    # Try lscpu first
    if command -v lscpu > /dev/null 2>&1; then
        model=$(lscpu | grep "Model name:" | sed 's/Model name:\s*//')
        if [ -n "$model" ]; then
            echo "$model"
            return
        fi
    fi

    # Fallback to /proc/cpuinfo
    if [ -f /proc/cpuinfo ]; then
        model=$(grep "model name" /proc/cpuinfo | head -1 | cut -d: -f2 | sed 's/^[ \t]*//')
        if [ -n "$model" ]; then
            echo "$model"
            return
        fi
    fi

    # Try dmidecode if available (requires root)
    if command -v dmidecode > /dev/null 2>&1; then
        model=$(dmidecode -t processor 2>/dev/null | grep "Version:" | head -1 | sed 's/.*Version:\s*//')
        if [ -n "$model" ]; then
            echo "$model"
            return
        fi
    fi

    echo "Unknown"
}

# Function to get CPU vendor
get_cpu_vendor() {
    if [ -f /proc/cpuinfo ]; then
        vendor=$(grep "vendor_id" /proc/cpuinfo | head -1 | cut -d: -f2 | sed 's/^[ \t]*//')
        case "$vendor" in
            GenuineIntel)
                echo "Intel"
                ;;
            AuthenticAMD)
                echo "AMD"
                ;;
            *)
                echo "$vendor"
                ;;
        esac
    else
        echo "Unknown"
    fi
}

# Function to get CPU family
get_cpu_family() {
    if [ -f /proc/cpuinfo ]; then
        family=$(grep "cpu family" /proc/cpuinfo | head -1 | cut -d: -f2 | sed 's/^[ \t]*//')
        if [ -n "$family" ]; then
            echo "$family"
        else
            echo "0"
        fi
    else
        echo "0"
    fi
}

# Function to get number of cores
get_cpu_cores() {
    if command -v nproc > /dev/null 2>&1; then
        nproc
    elif [ -f /proc/cpuinfo ]; then
        grep -c "processor" /proc/cpuinfo
    else
        echo "1"
    fi
}

# Function to get CPU frequency
get_cpu_freq() {
    if command -v lscpu > /dev/null 2>&1; then
        freq=$(lscpu | grep "CPU MHz:" | sed 's/CPU MHz:\s*//')
        if [ -n "$freq" ]; then
            echo "$freq"
            return
        fi
    fi

    if [ -f /proc/cpuinfo ]; then
        freq=$(grep "cpu MHz" /proc/cpuinfo | head -1 | cut -d: -f2 | sed 's/^[ \t]*//')
        if [ -n "$freq" ]; then
            echo "$freq"
        else
            echo "0"
        fi
    else
        echo "0"
    fi
}

# Main execution - output NFD local source format
CPU_MODEL=$(get_cpu_model)
CPU_VENDOR=$(get_cpu_vendor)
CPU_FAMILY=$(get_cpu_family)
CPU_CORES=$(get_cpu_cores)
CPU_FREQ=$(get_cpu_freq)

# Output in NFD local source format (key=value pairs)
echo "LABEL_LOCAL_CPU_MODEL=$CPU_MODEL"
echo "LABEL_LOCAL_CPU_VENDOR=$CPU_VENDOR"
echo "LABEL_LOCAL_CPU_FAMILY=$CPU_FAMILY"
echo "LABEL_LOCAL_CPU_CORES=$CPU_CORES"
echo "LABEL_LOCAL_CPU_FREQ_MHZ=$CPU_FREQ"

# Also output as attributes for custom rules
echo "FEATURE_LOCAL_CPU_MODEL=$CPU_MODEL"
echo "FEATURE_LOCAL_CPU_VENDOR=$CPU_VENDOR"
