# Backup Strategy

> **Version:** 1.0
> **Last Updated:** 2026-01-23
> **Status:** Operational Guide
> **Audience:** DBAs, SREs, platform engineers

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

### 3.2 Configuration

```yaml
# PostgreSQL backup configuration
backup:
  enabled: true
  schedule: "0 2 * * *"  # Daily at 02:00 UTC
  retentionPolicy: "30d"

  pgbasebackup:
    s3:
      bucket: bud-backups
      prefix: postgresql/
      region: us-east-1

  walArchive:
    enabled: true
    s3:
      bucket: bud-wal-archive
      prefix: wal/
      compression: gzip
```

### 3.3 Backup Commands

```bash
# Manual full backup
pg_basebackup -D /backup/pg_$(date +%Y%m%d) \
  -Ft -z -P -U postgres -h postgresql

# Verify backup
pg_verifybackup /backup/pg_YYYYMMDD

# List available backups
aws s3 ls s3://bud-backups/postgresql/

# Check WAL archive
aws s3 ls s3://bud-wal-archive/wal/ | tail -10
```

### 3.4 Restore Procedures

**Point-in-Time Recovery:**

```bash
# 1. Stop PostgreSQL
kubectl scale deployment postgresql --replicas=0 -n bud-data

# 2. Download base backup
aws s3 cp s3://bud-backups/postgresql/base-YYYYMMDD.tar.gz /restore/

# 3. Extract backup
tar -xzf /restore/base-YYYYMMDD.tar.gz -C /var/lib/postgresql/data

# 4. Configure recovery
cat > /var/lib/postgresql/data/postgresql.auto.conf << EOF
restore_command = 'aws s3 cp s3://bud-wal-archive/wal/%f %p'
recovery_target_time = '2026-01-23 10:00:00 UTC'
recovery_target_action = 'promote'
EOF

# 5. Create recovery signal
touch /var/lib/postgresql/data/recovery.signal

# 6. Start PostgreSQL
kubectl scale deployment postgresql --replicas=1 -n bud-data
```

---

## 4. ClickHouse Backup

### 4.1 Backup Strategy

**Daily Full Backups:**
- clickhouse-backup tool
- Incremental supported
- S3 storage

### 4.2 Configuration

```yaml
# clickhouse-backup config
general:
  remote_storage: s3
  backups_to_keep_local: 2
  backups_to_keep_remote: 14

s3:
  bucket: bud-backups
  path: clickhouse/
  region: us-east-1
  compression_format: gzip
```

### 4.3 Backup Commands

```bash
# Create backup
clickhouse-backup create daily-$(date +%Y%m%d)

# Upload to S3
clickhouse-backup upload daily-$(date +%Y%m%d)

# List backups
clickhouse-backup list

# Restore from backup
clickhouse-backup download daily-YYYYMMDD
clickhouse-backup restore daily-YYYYMMDD
```

---

## 5. MongoDB Backup

### 5.1 Backup Strategy

**Daily Full Backups:**
- mongodump with oplog
- Compressed archive
- S3 storage

### 5.2 Backup Commands

```bash
# Create backup
mongodump --host mongodb --port 27017 \
  --archive=/backup/mongodb-$(date +%Y%m%d).gz \
  --gzip --oplog

# Upload to S3
aws s3 cp /backup/mongodb-$(date +%Y%m%d).gz \
  s3://bud-backups/mongodb/

# Restore
aws s3 cp s3://bud-backups/mongodb/mongodb-YYYYMMDD.gz /restore/
mongorestore --host mongodb --port 27017 \
  --archive=/restore/mongodb-YYYYMMDD.gz \
  --gzip --oplogReplay
```

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

### 6.2 Configuration

```yaml
# Redis configuration
save 3600 1        # Save after 1 hour if 1+ changes
save 300 100       # Save after 5 min if 100+ changes
save 60 10000      # Save after 1 min if 10000+ changes

appendonly yes
appendfsync everysec
```

### 6.3 Backup Commands

```bash
# Trigger manual save
redis-cli BGSAVE

# Copy RDB file
kubectl cp bud-data/redis-0:/data/dump.rdb ./dump.rdb

# Upload to S3
aws s3 cp dump.rdb s3://bud-backups/redis/dump-$(date +%Y%m%d%H%M).rdb

# Restore
aws s3 cp s3://bud-backups/redis/dump-YYYYMMDDHHMM.rdb /data/dump.rdb
# Restart Redis (will load dump.rdb on start)
```

---

## 7. MinIO Backup

### 7.1 Backup Strategy

**Bucket Replication:**
- Continuous replication to DR region
- Real-time sync
- No separate backup needed

### 7.2 Configuration

```bash
# Configure replication
mc admin bucket remote add minio/bud-models \
  https://minio-dr:9000/bud-models \
  --service replication

# Enable replication
mc replicate add minio/bud-models \
  --remote-bucket https://minio-dr:9000/bud-models \
  --replicate "existing-objects,delete,delete-marker"

# Check replication status
mc replicate status minio/bud-models
```

---

## 8. Kubernetes Backup (Velero)

### 8.1 Backup Strategy

**Daily Cluster Backups:**
- All namespaces
- PersistentVolumes
- Secrets and ConfigMaps

### 8.2 Configuration

```yaml
# Velero schedule
apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: daily-backup
  namespace: velero
spec:
  schedule: "0 3 * * *"  # Daily at 03:00 UTC
  template:
    includedNamespaces:
      - bud-system
      - bud-data
      - bud-auth
    storageLocation: default
    ttl: 720h  # 30 days
```

### 8.3 Backup Commands

```bash
# Create manual backup
velero backup create manual-backup-$(date +%Y%m%d) \
  --include-namespaces bud-system,bud-data,bud-auth

# List backups
velero backup get

# Check backup details
velero backup describe daily-backup-YYYYMMDD

# Restore from backup
velero restore create --from-backup daily-backup-YYYYMMDD \
  --include-namespaces bud-system
```

---

## 9. Secrets Backup

### 9.1 Backup Strategy

**Manual on Change:**
- Export from Vault/Kubernetes
- Encrypted storage
- Version controlled

### 9.2 Procedure

```bash
# Export secrets (encrypted)
kubectl get secrets -n bud-system -o yaml | \
  kubeseal --recovery-unseal > secrets-backup-$(date +%Y%m%d).yaml

# Store securely
gpg --symmetric --cipher-algo AES256 secrets-backup-YYYYMMDD.yaml

# Upload to secure storage
aws s3 cp secrets-backup-YYYYMMDD.yaml.gpg \
  s3://bud-secrets-backup/ --sse aws:kms
```

---

## 10. Backup Verification

### 10.1 Automated Verification

```yaml
# Verification job (runs weekly)
apiVersion: batch/v1
kind: CronJob
metadata:
  name: backup-verification
spec:
  schedule: "0 6 * * 0"  # Weekly Sunday 06:00
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: verify
            image: backup-verify:latest
            command:
            - /scripts/verify-backups.sh
```

### 10.2 Verification Checklist

| Check | Frequency | Automated |
|-------|-----------|-----------|
| Backup exists | Daily | Yes |
| Backup size reasonable | Daily | Yes |
| Checksum valid | Weekly | Yes |
| Restore to test env | Weekly | Yes |
| Full restore test | Monthly | Partial |

### 10.3 Verification Script

```bash
#!/bin/bash
# verify-backups.sh

# Check PostgreSQL backup
latest_pg=$(aws s3 ls s3://bud-backups/postgresql/ | tail -1 | awk '{print $4}')
if [[ -z "$latest_pg" ]]; then
  echo "ERROR: No PostgreSQL backup found"
  exit 1
fi

# Check backup age
backup_date=$(echo $latest_pg | grep -oP '\d{8}')
if [[ $(date -d "$backup_date" +%s) -lt $(date -d "2 days ago" +%s) ]]; then
  echo "ERROR: PostgreSQL backup is too old"
  exit 1
fi

# Verify backup integrity
aws s3 cp s3://bud-backups/postgresql/$latest_pg /tmp/
pg_verifybackup /tmp/$latest_pg

echo "All backup verifications passed"
```

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

### 11.2 Cleanup Automation

```bash
# PostgreSQL cleanup
aws s3 ls s3://bud-backups/postgresql/ | \
  while read -r line; do
    date=$(echo $line | awk '{print $1}')
    if [[ $(date -d "$date" +%s) -lt $(date -d "30 days ago" +%s) ]]; then
      file=$(echo $line | awk '{print $4}')
      aws s3 rm s3://bud-backups/postgresql/$file
    fi
  done
```

---

## 12. Backup Monitoring

### 12.1 Alerts

| Alert | Condition | Severity |
|-------|-----------|----------|
| Backup Failed | Job exit code != 0 | Critical |
| Backup Missing | No backup in 24h | Critical |
| Backup Too Small | Size < 80% of average | Warning |
| Verification Failed | Integrity check failed | Critical |

### 12.2 Metrics

```yaml
# Prometheus metrics to monitor
- backup_last_success_timestamp
- backup_size_bytes
- backup_duration_seconds
- backup_files_count
```

---

## 13. Quick Reference

### 13.1 Emergency Restore Commands

```bash
# PostgreSQL - Latest backup
./scripts/restore-postgres.sh --latest

# ClickHouse - Specific date
./scripts/restore-clickhouse.sh --date 2026-01-22

# Full cluster - Velero
velero restore create --from-backup $(velero backup get -o json | jq -r '.items[0].metadata.name')
```

### 13.2 Backup Locations

| Component | Bucket | Path |
|-----------|--------|------|
| PostgreSQL | bud-backups | /postgresql/ |
| PostgreSQL WAL | bud-wal-archive | /wal/ |
| ClickHouse | bud-backups | /clickhouse/ |
| MongoDB | bud-backups | /mongodb/ |
| Redis | bud-backups | /redis/ |
| Kubernetes | bud-velero | /backups/ |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-23 | Documentation | Initial version |
