# MaxMind GeoIP Database Setup Guide

## Overview

The BudGateway uses MaxMind's GeoLite2 database to enrich API request data with geographic information (country, city, region, coordinates). This guide covers obtaining, installing, configuring, and maintaining the GeoIP database for production use.

## Prerequisites

- MaxMind account (free for GeoLite2 or commercial for GeoIP2)
- 200MB+ disk space for database files
- Linux/macOS/Windows system with appropriate permissions
- Internet connection for database downloads and updates
- Read permissions for gateway service
- Optional: Automated update mechanism

## Quick Start

### 1. Create MaxMind Account

1. Visit [https://www.maxmind.com/en/geolite2/signup](https://www.maxmind.com/en/geolite2/signup)
2. Complete registration for free GeoLite2 access
3. Verify email and log in
4. Navigate to "My License Keys" under account settings

### 2. Generate License Key

1. Click "Generate new license key"
2. Enter description: "BudGateway GeoIP"
3. Select "No" for "Will this key be used for GeoIP Update?"
4. Copy and save the license key securely

### 3. Download Database

#### Manual Download

```bash
# Create directory for GeoIP database
sudo mkdir -p /opt/geoip
sudo chmod 755 /opt/geoip

# Download GeoLite2-City database
wget -O GeoLite2-City.tar.gz \
  "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&license_key=YOUR_LICENSE_KEY&suffix=tar.gz"

# Extract database
tar -xzf GeoLite2-City.tar.gz

# Move to final location
sudo mv GeoLite2-City_*/GeoLite2-City.mmdb /opt/geoip/
sudo chmod 644 /opt/geoip/GeoLite2-City.mmdb

# Clean up
rm -rf GeoLite2-City.tar.gz GeoLite2-City_*
```

#### Using GeoIP Update Tool

```bash
# Install geoipupdate tool
# Ubuntu/Debian
sudo apt-get install geoipupdate

# RHEL/CentOS
sudo yum install geoipupdate

# macOS
brew install geoipupdate

# Configure
sudo tee /etc/GeoIP.conf > /dev/null <<EOF
AccountID YOUR_ACCOUNT_ID
LicenseKey YOUR_LICENSE_KEY
EditionIDs GeoLite2-City GeoLite2-Country GeoLite2-ASN
DatabaseDirectory /opt/geoip
EOF

# Run update
sudo geoipupdate
```

### 4. Configure BudGateway

Update your `tensorzero.toml` configuration:

```toml
[gateway.analytics]
enabled = true
geoip_db_path = "/opt/geoip/GeoLite2-City.mmdb"
geoip_fallback_enabled = true  # Continue if GeoIP fails

[gateway.analytics.geoip]
cache_size = 10000  # Number of IPs to cache
cache_ttl = 3600    # Cache TTL in seconds
```

Or use environment variables:

```bash
export GEOIP_DB_PATH=/opt/geoip/GeoLite2-City.mmdb
export GEOIP_CACHE_SIZE=10000
export GEOIP_CACHE_TTL=3600
```

## Database Types

### GeoLite2 (Free)

- **Coverage**: Good coverage for countries and major cities
- **Accuracy**: 80-90% for country, 50-70% for city
- **Updates**: Weekly
- **Size**: ~70MB compressed, ~130MB uncompressed
- **License**: Creative Commons Attribution-ShareAlike 4.0

### GeoIP2 (Commercial)

- **Coverage**: Comprehensive global coverage
- **Accuracy**: 99.8% for country, 80-90% for city
- **Updates**: Twice weekly
- **Size**: ~100MB compressed, ~180MB uncompressed
- **License**: Commercial (requires subscription)
- **Additional Data**: ISP, organization, user type

## Production Setup

### 1. High Availability Configuration

```bash
# Primary database location
/opt/geoip/
├── GeoLite2-City.mmdb         # Active database
├── GeoLite2-City.mmdb.backup  # Previous version
└── GeoLite2-City.mmdb.tmp     # Download temporary

# Atomic update script
#!/bin/bash
# /usr/local/bin/update-geoip.sh

set -e

GEOIP_DIR="/opt/geoip"
DB_NAME="GeoLite2-City.mmdb"
LICENSE_KEY="YOUR_LICENSE_KEY"

# Download to temporary file
wget -q -O "${GEOIP_DIR}/${DB_NAME}.tmp.tar.gz" \
  "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&license_key=${LICENSE_KEY}&suffix=tar.gz"

# Extract to temporary location
tar -xzf "${GEOIP_DIR}/${DB_NAME}.tmp.tar.gz" -C "${GEOIP_DIR}"

# Backup current database
if [ -f "${GEOIP_DIR}/${DB_NAME}" ]; then
    cp "${GEOIP_DIR}/${DB_NAME}" "${GEOIP_DIR}/${DB_NAME}.backup"
fi

# Atomic move
mv "${GEOIP_DIR}"/GeoLite2-City_*/"${DB_NAME}" "${GEOIP_DIR}/${DB_NAME}.new"
mv "${GEOIP_DIR}/${DB_NAME}.new" "${GEOIP_DIR}/${DB_NAME}"

# Cleanup
rm -rf "${GEOIP_DIR}"/${DB_NAME}.tmp.tar.gz "${GEOIP_DIR}"/GeoLite2-City_*

# Verify new database
if ! file "${GEOIP_DIR}/${DB_NAME}" | grep -q "MaxMind DB"; then
    echo "Error: Invalid database file"
    # Restore backup
    mv "${GEOIP_DIR}/${DB_NAME}.backup" "${GEOIP_DIR}/${DB_NAME}"
    exit 1
fi

echo "GeoIP database updated successfully"
```

### 2. Automated Updates

#### Using Cron

```bash
# Add to crontab
sudo crontab -e

# Update every Tuesday and Friday at 3 AM
0 3 * * 2,5 /usr/local/bin/update-geoip.sh >> /var/log/geoip-update.log 2>&1

# Or weekly update
0 3 * * 0 /usr/local/bin/update-geoip.sh >> /var/log/geoip-update.log 2>&1
```

#### Using Systemd Timer

```ini
# /etc/systemd/system/geoip-update.service
[Unit]
Description=Update GeoIP Database
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/update-geoip.sh
StandardOutput=journal
StandardError=journal

# /etc/systemd/system/geoip-update.timer
[Unit]
Description=Update GeoIP Database Weekly
Requires=geoip-update.service

[Timer]
OnCalendar=weekly
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable geoip-update.timer
sudo systemctl start geoip-update.timer
```

### 3. Monitoring

#### Health Check Script

```bash
#!/bin/bash
# /usr/local/bin/check-geoip.sh

GEOIP_DB="/opt/geoip/GeoLite2-City.mmdb"
MAX_AGE_DAYS=14

# Check if database exists
if [ ! -f "$GEOIP_DB" ]; then
    echo "CRITICAL: GeoIP database not found"
    exit 2
fi

# Check database age
DB_AGE=$(( ($(date +%s) - $(stat -c %Y "$GEOIP_DB")) / 86400 ))
if [ $DB_AGE -gt $MAX_AGE_DAYS ]; then
    echo "WARNING: GeoIP database is $DB_AGE days old"
    exit 1
fi

# Verify database integrity
if ! python3 -c "import maxminddb; maxminddb.open_database('$GEOIP_DB')" 2>/dev/null; then
    echo "CRITICAL: GeoIP database is corrupted"
    exit 2
fi

echo "OK: GeoIP database is healthy (age: $DB_AGE days)"
exit 0
```

#### Prometheus Metrics

```yaml
# prometheus.yml
- job_name: geoip_exporter
  static_configs:
    - targets: ['localhost:9100']
  metric_relabel_configs:
    - source_labels: [__name__]
      regex: 'node_filestat_mtime_seconds{file="/opt/geoip/.*"}'
      target_label: __name__
      replacement: geoip_database_age_seconds
```

### 4. Docker Configuration

```dockerfile
# Dockerfile
FROM rust:1.70 as builder

# ... build steps ...

FROM debian:bullseye-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Create GeoIP directory
RUN mkdir -p /opt/geoip

# Download GeoIP database at build time (optional)
# ARG MAXMIND_LICENSE_KEY
# RUN wget -O /tmp/GeoLite2-City.tar.gz \
#     "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&license_key=${MAXMIND_LICENSE_KEY}&suffix=tar.gz" \
#     && tar -xzf /tmp/GeoLite2-City.tar.gz -C /tmp \
#     && mv /tmp/GeoLite2-City_*/*.mmdb /opt/geoip/ \
#     && rm -rf /tmp/GeoLite2-City*

# Or mount at runtime
VOLUME ["/opt/geoip"]

# Copy application
COPY --from=builder /app/target/release/budgateway /usr/local/bin/

# Set environment
ENV GEOIP_DB_PATH=/opt/geoip/GeoLite2-City.mmdb

ENTRYPOINT ["/usr/local/bin/budgateway"]
```

Docker Compose:
```yaml
version: '3.8'

services:
  budgateway:
    image: budgateway:latest
    volumes:
      - geoip_data:/opt/geoip:ro
    environment:
      GEOIP_DB_PATH: /opt/geoip/GeoLite2-City.mmdb
    depends_on:
      - geoip-updater

  geoip-updater:
    image: maxmindinc/geoipupdate:latest
    environment:
      GEOIPUPDATE_ACCOUNT_ID: ${MAXMIND_ACCOUNT_ID}
      GEOIPUPDATE_LICENSE_KEY: ${MAXMIND_LICENSE_KEY}
      GEOIPUPDATE_EDITION_IDS: GeoLite2-City
      GEOIPUPDATE_FREQUENCY: 168  # hours (weekly)
    volumes:
      - geoip_data:/usr/share/GeoIP

volumes:
  geoip_data:
```

## Kubernetes Deployment

### ConfigMap Approach

```yaml
# geoip-updater-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: geoip-updater
spec:
  schedule: "0 3 * * 0"  # Weekly on Sunday at 3 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: updater
            image: maxmindinc/geoipupdate:latest
            env:
            - name: GEOIPUPDATE_ACCOUNT_ID
              valueFrom:
                secretKeyRef:
                  name: maxmind-credentials
                  key: account-id
            - name: GEOIPUPDATE_LICENSE_KEY
              valueFrom:
                secretKeyRef:
                  name: maxmind-credentials
                  key: license-key
            - name: GEOIPUPDATE_EDITION_IDS
              value: "GeoLite2-City"
            volumeMounts:
            - name: geoip-data
              mountPath: /usr/share/GeoIP
          volumes:
          - name: geoip-data
            persistentVolumeClaim:
              claimName: geoip-pvc
          restartPolicy: OnFailure
```

### PersistentVolume Approach

```yaml
# geoip-pv.yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: geoip-pv
spec:
  capacity:
    storage: 1Gi
  accessModes:
    - ReadOnlyMany
  nfs:
    server: nfs-server.example.com
    path: /exports/geoip

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: geoip-pvc
spec:
  accessModes:
    - ReadOnlyMany
  resources:
    requests:
      storage: 1Gi
```

### Gateway Deployment

```yaml
# budgateway-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: budgateway
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: gateway
        image: budgateway:latest
        env:
        - name: GEOIP_DB_PATH
          value: /opt/geoip/GeoLite2-City.mmdb
        volumeMounts:
        - name: geoip-data
          mountPath: /opt/geoip
          readOnly: true
      volumes:
      - name: geoip-data
        persistentVolumeClaim:
          claimName: geoip-pvc
```

## Performance Optimization

### 1. Memory-Mapped Files

```rust
// Use memory-mapped files for better performance
use memmap2::MmapOptions;
use std::fs::File;

let file = File::open("/opt/geoip/GeoLite2-City.mmdb")?;
let mmap = unsafe { MmapOptions::new().map(&file)? };
let reader = maxminddb::Reader::from_source(mmap)?;
```

### 2. Caching Strategy

```rust
use lru::LruCache;
use std::sync::RwLock;

struct GeoIpCache {
    cache: RwLock<LruCache<String, GeoData>>,
}

impl GeoIpCache {
    fn new(capacity: usize) -> Self {
        Self {
            cache: RwLock::new(LruCache::new(capacity)),
        }
    }

    fn get_or_lookup(&self, ip: &str) -> Result<GeoData> {
        // Check cache first
        if let Some(data) = self.cache.read().unwrap().get(ip) {
            return Ok(data.clone());
        }

        // Lookup and cache
        let data = self.lookup_fresh(ip)?;
        self.cache.write().unwrap().put(ip.to_string(), data.clone());
        Ok(data)
    }
}
```

### 3. Benchmarks

```bash
# Test lookup performance
#!/usr/bin/env python3
import time
import maxminddb

reader = maxminddb.open_database('/opt/geoip/GeoLite2-City.mmdb')

# Warm up
for _ in range(1000):
    reader.get('8.8.8.8')

# Benchmark
start = time.time()
for _ in range(100000):
    reader.get('8.8.8.8')
end = time.time()

print(f"Lookups per second: {100000 / (end - start):.0f}")
reader.close()
```

Expected performance:
- Cold lookup: ~100μs
- Cached lookup: ~1μs
- Memory usage: ~150MB for database
- Cache memory: ~10MB for 10,000 entries

## Troubleshooting

### Common Issues

#### 1. Database Not Found

```
Error: Failed to load GeoIP database: No such file or directory
```

**Solution:**
- Verify path in configuration
- Check file permissions: `ls -la /opt/geoip/`
- Ensure database downloaded successfully

#### 2. Invalid Database Format

```
Error: Invalid MaxMind DB file
```

**Solution:**
- Re-download database
- Verify download completed: `file /opt/geoip/GeoLite2-City.mmdb`
- Check for corruption: `md5sum /opt/geoip/GeoLite2-City.mmdb`

#### 3. License Key Invalid

```
Error: Invalid license key
```

**Solution:**
- Regenerate license key in MaxMind account
- Ensure key has GeoLite2 permissions
- Check for extra spaces or characters

#### 4. Memory Issues

```
Error: Cannot allocate memory
```

**Solution:**
- Use memory-mapped files instead of loading to RAM
- Reduce cache size
- Increase system memory limits

### Debugging

Enable debug logging:

```toml
[logging]
level = "debug"
geoip_debug = true
```

Test lookup manually:

```bash
# Using mmdblookup tool
mmdblookup --file /opt/geoip/GeoLite2-City.mmdb \
  --ip 8.8.8.8 \
  country names en

# Using Python
python3 -c "
import maxminddb
reader = maxminddb.open_database('/opt/geoip/GeoLite2-City.mmdb')
print(reader.get('8.8.8.8'))
"
```

## Legal and Compliance

### Attribution Requirements

When using GeoLite2 databases, you must include:

```html
This product includes GeoLite2 data created by MaxMind, available from
<a href="https://www.maxmind.com">https://www.maxmind.com</a>.
```

### GDPR Compliance

- IP addresses may be considered personal data
- Consider anonymizing last octet: `192.168.1.xxx`
- Implement data retention policies
- Document lawful basis for processing

### Data Accuracy Disclaimer

Include in documentation:

```
Geographic data is approximate and should not be used for:
- Legal compliance requiring precise location
- Emergency services
- Navigation or safety-critical applications
```

## Migration from Other Solutions

### From IP2Location

```python
# Migration script
import ip2location
import maxminddb

# Old database
old_db = ip2location.IP2Location("IP2LOCATION.BIN")

# New database
new_db = maxminddb.open_database("GeoLite2-City.mmdb")

# Compare results
test_ips = ["8.8.8.8", "1.1.1.1", "208.67.222.222"]
for ip in test_ips:
    old_result = old_db.get(ip)
    new_result = new_db.get(ip)
    print(f"{ip}:")
    print(f"  Old: {old_result.country_short}")
    print(f"  New: {new_result['country']['iso_code']}")
```

### From GeoIP Legacy

```bash
# Convert legacy database
geoip2-to-legacy.pl GeoLite2-City.mmdb > GeoIPCity.dat
```

## Support and Resources

- **MaxMind Documentation**: https://dev.maxmind.com/
- **GeoLite2 Databases**: https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
- **GeoIP Update**: https://github.com/maxmind/geoipupdate
- **Community Forum**: https://community.maxmind.com/
- **Status Page**: https://status.maxmind.com/

## Appendix: Test IPs

Common IPs for testing:

```
8.8.8.8         - Google DNS (US)
1.1.1.1         - Cloudflare DNS (AU/US)
208.67.222.222  - OpenDNS (US)
185.60.216.35   - OpenVPN (NL)
134.195.196.50  - TOR Exit (DE)
2001:4860:4860::8888 - Google IPv6 (US)
```
