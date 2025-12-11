use maxminddb::{geoip2, MaxMindDBError, Reader};
use std::net::IpAddr;
use std::path::Path;
use std::sync::Arc;
use tracing::{debug, error, warn};

use crate::analytics::GatewayAnalyticsDatabaseInsert;

/// GeoIP lookup service using MaxMind GeoIP2 database
#[derive(Clone)]
pub struct GeoIpService {
    reader: Arc<Option<Reader<Vec<u8>>>>,
}

impl GeoIpService {
    /// Create a new GeoIP service from a database file path
    pub fn new(db_path: Option<&Path>) -> Self {
        let reader = match db_path {
            Some(path) => match Reader::open_readfile(path) {
                Ok(reader) => {
                    debug!("Successfully loaded GeoIP database from {:?}", path);
                    Arc::new(Some(reader))
                }
                Err(e) => {
                    warn!("Failed to load GeoIP database from {:?}: {}", path, e);
                    Arc::new(None)
                }
            },
            None => {
                debug!("No GeoIP database path provided, GeoIP lookups will be disabled");
                Arc::new(None)
            }
        };

        Self { reader }
    }

    /// Enrich analytics record with GeoIP data
    pub fn enrich_analytics(&self, ip_str: &str, record: &mut GatewayAnalyticsDatabaseInsert) {
        // Parse IP address
        let ip = match ip_str.parse::<IpAddr>() {
            Ok(ip) => ip,
            Err(e) => {
                debug!("Failed to parse IP address '{}': {}", ip_str, e);
                return;
            }
        };

        // Skip lookups for private IPs
        if is_private_ip(&ip) {
            debug!("Skipping GeoIP lookup for private IP: {}", ip);
            return;
        }

        // Get reader
        let reader = match self.reader.as_ref() {
            Some(r) => r,
            None => return,
        };

        // Perform lookup
        match reader.lookup::<geoip2::City>(ip) {
            Ok(city_data) => {
                // Country information
                if let Some(country) = city_data.country {
                    record.country_code = country.iso_code.map(|s| s.to_string());
                    if let Some(names) = country.names {
                        record.country_name = names.get("en").map(|s| s.to_string());
                    }
                }

                // Region/State information
                if let Some(subdivisions) = city_data.subdivisions {
                    if let Some(subdivision) = subdivisions.first() {
                        record.region = subdivision
                            .iso_code
                            .or_else(|| {
                                subdivision
                                    .names
                                    .as_ref()
                                    .and_then(|n| n.get("en").copied())
                            })
                            .map(|s| s.to_string());
                    }
                }

                // City information
                if let Some(city) = city_data.city {
                    if let Some(names) = city.names {
                        record.city = names.get("en").map(|s| s.to_string());
                    }
                }

                // Location information
                if let Some(location) = city_data.location {
                    record.latitude = location.latitude.map(|v| v as f32);
                    record.longitude = location.longitude.map(|v| v as f32);
                    record.timezone = location.time_zone.map(|s| s.to_string());
                }

                // Network information
                // Note: ASN/ISP information is typically only available in GeoIP2 ISP or Enterprise databases
                // The City database we're using doesn't include this information

                debug!(
                    "GeoIP lookup successful for {}: country={:?}, city={:?}",
                    ip, record.country_code, record.city
                );
            }
            Err(MaxMindDBError::AddressNotFoundError(_)) => {
                debug!("No GeoIP data found for IP: {}", ip);
            }
            Err(e) => {
                error!("GeoIP lookup error for IP {}: {}", ip, e);
            }
        }
    }
}

/// Check if an IP address is private/internal
fn is_private_ip(ip: &IpAddr) -> bool {
    match ip {
        IpAddr::V4(ipv4) => {
            ipv4.is_private()
                || ipv4.is_loopback()
                || ipv4.is_link_local()
                || ipv4.is_broadcast()
                || ipv4.is_multicast()
        }
        IpAddr::V6(ipv6) => {
            ipv6.is_loopback()
                || ipv6.is_multicast()
                || ipv6.is_unspecified()
                // Check for IPv6 private ranges
                || (ipv6.segments()[0] & 0xfe00) == 0xfc00 // Unique local
                || (ipv6.segments()[0] & 0xffc0) == 0xfe80 // Link local
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::{Ipv4Addr, Ipv6Addr};

    #[test]
    fn test_is_private_ip() {
        // IPv4 tests
        assert!(is_private_ip(&IpAddr::V4(Ipv4Addr::new(192, 168, 1, 1))));
        assert!(is_private_ip(&IpAddr::V4(Ipv4Addr::new(10, 0, 0, 1))));
        assert!(is_private_ip(&IpAddr::V4(Ipv4Addr::new(172, 16, 0, 1))));
        assert!(is_private_ip(&IpAddr::V4(Ipv4Addr::new(127, 0, 0, 1))));
        assert!(!is_private_ip(&IpAddr::V4(Ipv4Addr::new(8, 8, 8, 8))));

        // IPv6 tests
        assert!(is_private_ip(&IpAddr::V6(Ipv6Addr::LOCALHOST)));
        assert!(!is_private_ip(&IpAddr::V6(Ipv6Addr::new(
            0x2001, 0x4860, 0x4860, 0, 0, 0, 0, 0x8888
        ))));
    }
}
