# Backup Strategy

---

## 1. Overview

This document defines the backup strategy for all Bud AI Foundry data stores, including what is backed up, backup schedules, retention policies, and restore procedures.

---

## 2. Backup Summary

| Component | Type | Frequency | Retention | Location |
|-----------|------|-----------|-----------|----------|
| PostgreSQL | Full + WAL | Daily + Continuous | 30 days | S3 |
| ClickHouse | Full | Daily | 14 days | S3 |
| MongoDB | Full | Daily | 14 days | S3 |
| Redis | RDB + AOF | Hourly + Continuous | 7 days | S3 |
| MinIO | Replication | Continuous | Indefinite | DR Region |
| Kubernetes | Velero | Daily | 30 days | S3 |
| Secrets | Manual | On change | Indefinite | Vault |

---

## 3. PostgreSQL Backup

### 3.1 Backup Strategy

**Continuous WAL Archiving:**
- Write-Ahead Logs streamed to S3
- Point-in-time recovery capability
- < 5 minute data loss (RPO)

**Daily Full Backups:**
- pg_basebackup at 02:00 UTC
- Compressed with gzip
- Encrypted with AES-256

### 3.4 Restore Procedures

**Point-in-Time Recovery:**

---

## 4. ClickHouse Backup

### 4.1 Backup Strategy

**Daily Full Backups:**
- clickhouse-backup tool
- Incremental supported
- S3 storage

---

## 5. MongoDB Backup

### 5.1 Backup Strategy

**Daily Full Backups:**
- mongodump with oplog
- Compressed archive
- S3 storage

---

## 6. Redis Backup

### 6.1 Backup Strategy

**RDB Snapshots:**
- Hourly snapshots
- Binary format
- S3 upload

**AOF (Append-Only File):**
- Continuous logging
- Replay for recovery
- fsync every second

---

## 7. MinIO Backup

### 7.1 Backup Strategy

**Bucket Replication:**
- Continuous replication to DR region
- Real-time sync
- No separate backup needed

---

## 8. Kubernetes Backup (Velero)

### 8.1 Backup Strategy

**Daily Cluster Backups:**
- All namespaces
- PersistentVolumes
- Secrets and ConfigMaps

---

## 9. Secrets Backup

### 9.1 Backup Strategy

**Manual on Change:**
- Export from Vault/Kubernetes
- Encrypted storage
- Version controlled

---

## 10. Backup Verification

### 10.2 Verification Checklist

| Check | Frequency | Automated |
|-------|-----------|-----------|
| Backup exists | Daily | Yes |
| Backup size reasonable | Daily | Yes |
| Checksum valid | Weekly | Yes |
| Restore to test env | Weekly | Yes |
| Full restore test | Monthly | Partial |

---

## 11. Retention Policy

### 11.1 Retention Schedule

| Backup Type | Daily | Weekly | Monthly | Yearly |
|-------------|-------|--------|---------|--------|
| PostgreSQL Full | 7 | 4 | 12 | 1 |
| PostgreSQL WAL | 7 | - | - | - |
| ClickHouse | 14 | - | - | - |
| MongoDB | 14 | - | - | - |
| Redis RDB | 7 | - | - | - |
| Kubernetes | 30 | - | - | - |

---

## 12. Backup Monitoring

### 12.1 Alerts

| Alert | Condition | Severity |
|-------|-----------|----------|
| Backup Failed | Job exit code != 0 | Critical |
| Backup Missing | No backup in 24h | Critical |
| Backup Too Small | Size < 80% of average | Warning |
| Verification Failed | Integrity check failed | Critical |
