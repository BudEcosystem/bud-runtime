# Archived SQL Migration Files

This directory contains deprecated SQL migration files that have been superseded by either:
1. Python migration methods in `migrate_clickhouse.py`
2. Consolidated into the active SQL migration file
3. Replaced by improved implementations

These files are kept for historical reference and documentation purposes.

---

## Archived Files

### 1. `fix_disk_network_deduplication_bug.sql` (245 lines)

**Date Created:** 2025-10-23
**Purpose:** Standalone fix for disk and network metrics deduplication bug in NodeMetrics materialized view
**Status:** **Superseded**

**Original Problem:**
- Disk metrics showed 10-11x inflation (e.g., 495 GB showed as 991 GB)
- Network metrics showed unrealistic values (650 Gbps instead of 10-100 Mbps)
- Root cause: Prometheus/OTel inserted same metric 7-11 times per minute, and `sumIf()` summed all duplicates

**Fix Implemented:**
- CPU: Rate calculations from counter metrics with proper time delta handling
- Disk: Deduplication by mountpoint before summing filesystem metrics
- Network: Rate calculations per container (counters, not cumulative totals)

**Why Archived:**
This standalone fix was successfully merged into `setup_cluster_metrics_materialized_views.sql` which now contains:
- All 4 materialized views (NodeMetrics, PodMetrics, GPUMetrics, ClusterMetrics)
- The complete deduplication logic from this file
- Better documentation and structure

**Migration Status:**
- ✅ Logic is active in `setup_cluster_metrics_materialized_views.sql` (line 35)
- ✅ Being executed by `migrate_clickhouse.py` (line 953)

---

### 2. `add_auth_metadata_columns.sql` (23 lines)

**Purpose:** Add authentication metadata columns to ModelInferenceDetails table
**Status:** **Superseded by Python migration method**

**Columns Added:**
- `api_key_id` (UUID)
- `user_id` (UUID)
- `api_key_project_id` (UUID)

**Plus indexes for efficient querying**

**Why Archived:**
Superseded by Python method `add_auth_metadata_columns()` in `migrate_clickhouse.py` (line 1062):
- More robust error handling
- Conditional execution (checks if columns already exist)
- Integrated into main migration flow
- Better logging and verification

**Migration Status:**
- ✅ Python method is active and running in migration
- ❌ SQL file no longer referenced or needed

---

### 3. `add_network_to_node_metrics.sql` (115 lines)

**Purpose:** Add network metrics columns to existing NodeMetrics table for legacy deployments
**Status:** **Superseded by Python migration method**

**Columns Added:**
- `network_receive_bytes_per_sec` (Float64, DEFAULT 0)
- `network_transmit_bytes_per_sec` (Float64, DEFAULT 0)

**Additional Changes:**
- Recreated materialized view to include network metrics
- Added indexes for network columns

**Why Archived:**
Superseded by Python method `migrate_node_metrics_network_columns()` in `migrate_clickhouse.py` (line 1014):
- More intelligent detection of existing columns
- Only adds missing columns (idempotent)
- Better error handling and logging
- Integrated into migration flow without dropping/recreating materialized view

**Migration Status:**
- ✅ Python method is active and running in migration
- ✅ Network columns are part of base schema creation
- ❌ SQL file no longer referenced or needed

---

### 4. `create_cluster_metrics_views.sql` (260 lines)

**Purpose:** Original approach for transforming OTel raw metrics using regular views + one materialized view
**Status:** **Superseded by improved materialized view approach**

**Original Approach:**
- Created base tables (NodeMetrics, PodMetrics, GPUMetrics, ClusterMetrics)
- Created regular views (`v_node_metrics`, `v_pod_metrics`, `v_gpu_metrics`, `v_cluster_metrics`)
- Created one materialized view (`mv_node_metrics_5m`) for 5-minute aggregations
- Used `SummingMergeTree` engine

**Problems with Original Approach:**
1. Regular views required real-time computation (slow)
2. Mixed regular views + materialized views was confusing
3. Didn't populate the base tables that API queries
4. Lacked deduplication logic (had the 10x inflation bug)
5. Less efficient aggregation strategy

**Why Archived:**
Superseded by `setup_cluster_metrics_materialized_views.sql` which:
- Uses materialized views with `TO` clause to auto-populate base tables
- All 4 metrics types have dedicated materialized views
- Includes sophisticated deduplication logic
- Uses `ReplacingMergeTree` for base tables (better for deduplication)
- More efficient 1-minute granularity
- Directly populates tables that API queries

**Migration Status:**
- ❌ No longer used or referenced
- ✅ Replaced by `setup_cluster_metrics_materialized_views.sql`

---

### 5. `backfill_cluster_metrics.py` (463 lines)

**Purpose:** Backfill historical cluster metrics data from `otel_metrics_gauge` into structured tables (NodeMetrics, PodMetrics, ClusterMetrics)
**Status:** **Deprecated - No Longer Needed**

**Original Use Case:**
This script was designed to populate NodeMetrics, PodMetrics, and ClusterMetrics tables with historical data that arrived BEFORE materialized views were created. It would manually run the same aggregation queries as the materialized views but on past data.

**Why Deprecated:**

1. **Not Needed for Fresh Installations**
   - Materialized views automatically populate tables with ALL new data
   - No historical gap exists on new deployments

2. **Not Needed for Existing Deployments**
   - pde-ditto and other clusters already have metrics flowing
   - Historical gaps (pre-migration) are acceptable for operations
   - Recent metrics data is what matters for monitoring

3. **Script Has Critical Bugs**
   - ❌ Missing network columns (`network_receive_bytes_per_sec`, `network_transmit_bytes_per_sec`)
   - ❌ Missing disk deduplication logic (would cause 10-11x inflation)
   - ❌ Missing network rate calculations (wrong values)
   - ❌ Missing CPU counter rate calculations
   - Would fail on current schema due to column mismatch

4. **High Maintenance Cost**
   - Requires keeping in sync with materialized view logic
   - Complex SQL that needs updating whenever schema changes
   - Testing requires production data and is time-consuming

**What It Did (When It Worked):**
```bash
# Backfill all clusters
python backfill_cluster_metrics.py

# Backfill specific cluster
python backfill_cluster_metrics.py --cluster-id <UUID>

# Backfill specific time range
python backfill_cluster_metrics.py --from-date "2025-10-20" --to-date "2025-10-21"

# Dry run
python backfill_cluster_metrics.py --dry-run
```

**Migration Status:**
- ❌ Script is broken (incompatible with current schema)
- ❌ No longer referenced in active migration files
- ✅ Materialized views handle all data automatically
- ✅ No operational need for historical backfill

**If You Really Need Historical Data:**
1. Fix the script to match current schema (add network columns)
2. Port deduplication logic from `setup_cluster_metrics_materialized_views.sql`
3. Add comprehensive tests
4. Run dry-run first to verify query correctness
5. Consider if the effort is worth it vs. just having a small data gap

**Archived Date:** 2025-10-24
**Reason:** Not needed for operations + broken due to schema changes

---

## Active Migration Files

For reference, the current active migration setup is:

### Python Migration: `migrate_clickhouse.py`
**Active Methods:**
- `create_cluster_metrics_tables()` - Creates base tables (NodeMetrics, PodMetrics, GPUMetrics, ClusterMetrics)
- `migrate_node_metrics_network_columns()` - Adds network columns to existing NodeMetrics (legacy migration)
- `setup_cluster_metrics_materialized_views()` - Executes the SQL file below
- `add_auth_metadata_columns()` - Adds auth metadata to ModelInferenceDetails
- `add_error_tracking_columns()` - Adds error tracking columns

### SQL Migration: `setup_cluster_metrics_materialized_views.sql` (365 lines)
**Creates 4 Materialized Views:**
1. `mv_populate_node_metrics` - CPU, memory, disk, load, network (with deduplication)
2. `mv_populate_pod_metrics` - Pod/container resources and status
3. `mv_populate_gpu_metrics` - GPU utilization and memory
4. `mv_populate_cluster_metrics` - Generic cluster-level metrics

**Key Features:**
- ✅ All materialized views use `TO` clause to auto-populate base tables
- ✅ NodeMetrics includes sophisticated deduplication logic for disk/network
- ✅ Proper CPU/network counter rate calculations
- ✅ 1-minute granularity for optimal performance
- ✅ No duplicate table creation (handled by Python)

---

## When to Use Archived Files

These archived files should **NOT** be executed as part of normal migration. They are kept for:

1. **Historical Reference** - Understanding the evolution of the migration approach
2. **Debugging** - If issues arise, compare with original implementation
3. **Documentation** - Learning what problems were solved and how

If you need to manually fix a specific issue on an existing deployment, you can:
- Extract the relevant SQL from archived files
- Adapt it to current schema
- Test thoroughly before applying

But in general, the active migration files should handle all scenarios including fresh installs and upgrades.

---

## Archived Date

**Date:** 2025-10-24
**Reason:** Migration cleanup - consolidate deprecated SQL files after verifying active migration has all required functionality

**Verified By:** Comparison of all SQL files and confirmation that active migration includes all fixes and improvements
