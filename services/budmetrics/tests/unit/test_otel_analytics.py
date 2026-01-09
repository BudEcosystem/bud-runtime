"""Unit tests for OTel Analytics query builders and smart table selection.

These tests verify:
1. Smart table selection logic based on query parameters
2. Query builder output for different table types
3. Metric select clauses with and without merge functions
4. Filter condition building
"""

import os
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from budmetrics.observability.otel_analytics import (
    AnalyticsTable,
    OTelAnalyticsQueryBuilder,
    TableSelectionResult,
    get_interval_minutes,
    is_otel_analytics_enabled,
    select_geo_table,
    select_metrics_table,
)


class TestSmartTableSelection:
    """Tests for smart table selection logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.now = datetime.now()
        self.one_day_ago = self.now - timedelta(days=1)
        self.one_week_ago = self.now - timedelta(days=7)
        self.one_month_ago = self.now - timedelta(days=30)
        self.one_year_ago = self.now - timedelta(days=365)

    def test_interval_minutes_conversion(self):
        """Test interval string to minutes conversion."""
        assert get_interval_minutes("1m") == 1
        assert get_interval_minutes("5m") == 5
        assert get_interval_minutes("15m") == 15
        assert get_interval_minutes("30m") == 30
        assert get_interval_minutes("1h") == 60
        assert get_interval_minutes("6h") == 360
        assert get_interval_minutes("12h") == 720
        assert get_interval_minutes("1d") == 1440
        assert get_interval_minutes("1w") == 10080
        assert get_interval_minutes("unknown") == 60  # default

    def test_otel_analytics_enabled_default(self):
        """Test that OTel analytics is enabled by default."""
        # Clear env var if set
        os.environ.pop("OTEL_ANALYTICS_ENABLED", None)
        assert is_otel_analytics_enabled() is True

    def test_otel_analytics_disabled_via_env(self):
        """Test disabling OTel analytics via environment variable."""
        os.environ["OTEL_ANALYTICS_ENABLED"] = "false"
        try:
            assert is_otel_analytics_enabled() is False
        finally:
            os.environ.pop("OTEL_ANALYTICS_ENABLED", None)

    def test_short_interval_selects_5m_rollup(self):
        """Test that short intervals (1m-30m) select 5m rollup table."""
        for interval in ["1m", "5m", "15m", "30m"]:
            result = select_metrics_table(
                interval=interval,
                from_date=self.one_day_ago,
                to_date=self.now,
            )
            assert result.table == AnalyticsTable.INFERENCE_METRICS_5M
            assert result.use_rollup is True
            assert result.requires_merge_functions is True
            assert "5m" in result.reason

    def test_medium_interval_short_range_selects_5m_rollup(self):
        """Test medium intervals with short range use 5m rollup."""
        result = select_metrics_table(
            interval="1h",
            from_date=self.one_day_ago,
            to_date=self.now,
        )
        assert result.table == AnalyticsTable.INFERENCE_METRICS_5M
        assert result.use_rollup is True

    def test_medium_interval_long_range_selects_1h_rollup(self):
        """Test medium intervals with long range use 1h rollup."""
        result = select_metrics_table(
            interval="1h",
            from_date=self.one_month_ago,
            to_date=self.now,
        )
        assert result.table == AnalyticsTable.INFERENCE_METRICS_1H
        assert result.use_rollup is True
        assert result.requires_merge_functions is True

    def test_long_interval_medium_range_selects_1h_rollup(self):
        """Test daily intervals with medium range use 1h rollup."""
        result = select_metrics_table(
            interval="1d",
            from_date=self.one_week_ago,
            to_date=self.now,
        )
        assert result.table == AnalyticsTable.INFERENCE_METRICS_1H

    def test_long_interval_long_range_selects_1d_rollup(self):
        """Test daily intervals with long range use 1d rollup."""
        result = select_metrics_table(
            interval="1d",
            from_date=self.one_year_ago,
            to_date=self.now,
        )
        assert result.table == AnalyticsTable.INFERENCE_METRICS_1D
        assert result.use_rollup is True
        # 1d table uses finalized values, not merge functions
        assert result.requires_merge_functions is False

    def test_detailed_data_selects_fact_table(self):
        """Test that requiring detailed data selects InferenceFact."""
        result = select_metrics_table(
            interval="1h",
            from_date=self.one_day_ago,
            to_date=self.now,
            requires_detailed_data=True,
        )
        assert result.table == AnalyticsTable.INFERENCE_FACT
        assert result.use_rollup is False
        assert result.requires_merge_functions is False

    def test_geo_table_selection_default(self):
        """Test geographic table selection defaults to GeoAnalytics1h."""
        result = select_geo_table(
            from_date=self.one_day_ago,
            to_date=self.now,
        )
        assert result.table == AnalyticsTable.GEO_ANALYTICS_1H
        assert result.use_rollup is True

    def test_geo_table_selection_detailed(self):
        """Test geographic table selection with detailed data."""
        result = select_geo_table(
            from_date=self.one_day_ago,
            to_date=self.now,
            requires_detailed_data=True,
        )
        assert result.table == AnalyticsTable.INFERENCE_FACT
        assert result.use_rollup is False


class TestOTelAnalyticsQueryBuilder:
    """Tests for OTel analytics query builder."""

    def setup_method(self):
        """Set up test fixtures."""
        self.builder = OTelAnalyticsQueryBuilder()
        self.now = datetime.now()
        self.one_day_ago = self.now - timedelta(days=1)
        self.project_id = uuid4()

    def test_get_column_mappings(self):
        """Test column name mappings for different tables."""
        # InferenceFact uses 'timestamp'
        assert self.builder.get_column(AnalyticsTable.INFERENCE_FACT, "timestamp") == "timestamp"
        # Rollup tables use 'ts'
        assert self.builder.get_column(AnalyticsTable.INFERENCE_METRICS_5M, "timestamp") == "ts"
        assert self.builder.get_column(AnalyticsTable.INFERENCE_METRICS_1H, "timestamp") == "ts"
        # GeoAnalytics uses 'country_code'
        assert self.builder.get_column(AnalyticsTable.GEO_ANALYTICS_1H, "country") == "country_code"

    def test_build_timeseries_query_5m_rollup(self):
        """Test building time series query for 5m rollup table."""
        table_result = TableSelectionResult(
            table=AnalyticsTable.INFERENCE_METRICS_5M,
            use_rollup=True,
            requires_merge_functions=True,
            reason="test",
        )

        query = self.builder.build_timeseries_query(
            table_result=table_result,
            metrics=["request_count", "success_rate"],
            from_date=self.one_day_ago,
            to_date=self.now,
            interval="1h",
            filters={"project": self.project_id},
        )

        # Check query structure
        assert "InferenceMetrics5m" in query
        assert "sum(request_count)" in query
        # success_rate now has division by zero protection
        assert "if(sum(request_count) > 0, sum(success_count) * 100.0 / sum(request_count), 0)" in query
        assert "time_bucket" in query
        assert f"project_id = '{self.project_id}'" in query

    def test_build_timeseries_query_fact_table(self):
        """Test building time series query for fact table."""
        table_result = TableSelectionResult(
            table=AnalyticsTable.INFERENCE_FACT,
            use_rollup=False,
            requires_merge_functions=False,
            reason="test",
        )

        query = self.builder.build_timeseries_query(
            table_result=table_result,
            metrics=["request_count", "latency_p95"],
            from_date=self.one_day_ago,
            to_date=self.now,
            interval="5m",
        )

        # Fact table uses regular aggregations
        assert "InferenceFact" in query
        assert "count()" in query
        assert "quantile(0.95)(response_time_ms)" in query

    def test_build_timeseries_query_with_merge_functions(self):
        """Test that rollup queries use merge functions for quantiles."""
        table_result = TableSelectionResult(
            table=AnalyticsTable.INFERENCE_METRICS_1H,
            use_rollup=True,
            requires_merge_functions=True,
            reason="test",
        )

        query = self.builder.build_timeseries_query(
            table_result=table_result,
            metrics=["latency_p95", "unique_users"],
            from_date=self.one_day_ago,
            to_date=self.now,
            interval="1h",
        )

        # Should use merge functions
        assert "quantilesTDigestMerge" in query
        assert "uniqMerge" in query

    def test_build_aggregated_query_with_group_by(self):
        """Test building aggregated query with grouping."""
        table_result = TableSelectionResult(
            table=AnalyticsTable.INFERENCE_METRICS_5M,
            use_rollup=True,
            requires_merge_functions=True,
            reason="test",
        )

        query = self.builder.build_aggregated_query(
            table_result=table_result,
            metrics=["request_count", "input_tokens"],
            from_date=self.one_day_ago,
            to_date=self.now,
            group_by=["model_name"],
        )

        assert "GROUP BY model_name" in query
        assert "sum(request_count)" in query
        assert "sum(input_tokens_sum)" in query

    def test_build_geo_query_country_level(self):
        """Test building geographic query at country level."""
        table_result = TableSelectionResult(
            table=AnalyticsTable.GEO_ANALYTICS_1H,
            use_rollup=True,
            requires_merge_functions=True,
            reason="test",
        )

        query = self.builder.build_geo_query(
            table_result=table_result,
            from_date=self.one_day_ago,
            to_date=self.now,
            group_by_level="country",
        )

        assert "GeoAnalytics1h" in query
        assert "country_code" in query
        assert "uniqMerge(unique_users)" in query
        assert "GROUP BY country_code" in query

    def test_build_geo_query_city_level(self):
        """Test building geographic query at city level."""
        table_result = TableSelectionResult(
            table=AnalyticsTable.GEO_ANALYTICS_1H,
            use_rollup=True,
            requires_merge_functions=True,
            reason="test",
        )

        query = self.builder.build_geo_query(
            table_result=table_result,
            from_date=self.one_day_ago,
            to_date=self.now,
            group_by_level="city",
        )

        assert "country_code, region, city" in query
        assert "GROUP BY country_code, region, city" in query

    def test_metric_selects_cached_count(self):
        """Test cached_count metric select for different tables."""
        # For rollup table
        selects = self.builder._build_metric_selects(
            table=AnalyticsTable.INFERENCE_METRICS_5M,
            metrics=["cached_count"],
            use_merge=True,
        )
        assert "sum(cached_count)" in selects[0]

        # For fact table
        selects = self.builder._build_metric_selects(
            table=AnalyticsTable.INFERENCE_FACT,
            metrics=["cached_count"],
            use_merge=False,
        )
        assert "countIf(cached = true)" in selects[0]

    def test_metric_selects_tokens(self):
        """Test token metrics for different tables."""
        # Rollup uses _sum columns
        selects = self.builder._build_metric_selects(
            table=AnalyticsTable.INFERENCE_METRICS_5M,
            metrics=["input_tokens", "output_tokens", "total_tokens"],
            use_merge=True,
        )
        assert "sum(input_tokens_sum)" in selects[0]
        assert "sum(output_tokens_sum)" in selects[1]
        assert "sum(input_tokens_sum) + sum(output_tokens_sum)" in selects[2]

        # Fact table uses direct columns
        selects = self.builder._build_metric_selects(
            table=AnalyticsTable.INFERENCE_FACT,
            metrics=["input_tokens", "output_tokens"],
            use_merge=False,
        )
        assert "sum(input_tokens)" in selects[0]
        assert "sum(output_tokens)" in selects[1]

    def test_filter_conditions_with_date_range(self):
        """Test filter condition building with date range."""
        conditions = self.builder._build_filter_conditions(
            table=AnalyticsTable.INFERENCE_METRICS_5M,
            from_date=self.one_day_ago,
            to_date=self.now,
            filters=None,
        )

        assert len(conditions) == 2
        assert "ts >=" in conditions[0]
        assert "ts <=" in conditions[1]

    def test_filter_conditions_with_project_filter(self):
        """Test filter condition building with project filter."""
        conditions = self.builder._build_filter_conditions(
            table=AnalyticsTable.INFERENCE_FACT,
            from_date=self.one_day_ago,
            to_date=self.now,
            filters={"project": self.project_id},
        )

        assert len(conditions) == 3
        assert f"project_id = '{self.project_id}'" in conditions[2]

    def test_filter_conditions_with_list_filter(self):
        """Test filter condition building with list filter."""
        model_ids = [uuid4(), uuid4()]
        conditions = self.builder._build_filter_conditions(
            table=AnalyticsTable.INFERENCE_METRICS_5M,
            from_date=self.one_day_ago,
            to_date=self.now,
            filters={"model": model_ids},
        )

        assert len(conditions) == 3
        assert "model_id IN" in conditions[2]
        for model_id in model_ids:
            assert str(model_id) in conditions[2]


class TestMetricDefinitions:
    """Tests for individual metric definitions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.builder = OTelAnalyticsQueryBuilder()

    def test_all_supported_metrics(self):
        """Test that all documented metrics are supported."""
        supported_metrics = [
            "request_count",
            "success_count",
            "error_count",
            "success_rate",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "cost",
            "latency_avg",
            "latency_p50",
            "latency_p95",
            "latency_p99",
            "unique_users",
            "ttft_avg",
            "ttft_p95",
            "cached_count",
            "blocked_count",
        ]

        for metric in supported_metrics:
            selects = self.builder._build_metric_selects(
                table=AnalyticsTable.INFERENCE_FACT,
                metrics=[metric],
                use_merge=False,
            )
            assert len(selects) == 1, f"Metric {metric} should produce one select"
            assert metric in selects[0] or metric.replace("_", "") in selects[0].replace("_", ""), \
                f"Metric {metric} select should contain metric name"

    def test_1d_rollup_fallback_to_raw_data_query(self):
        """Test that 1d rollup falls back to raw data query for removed columns.

        Note: These columns (unique_users, response_time_p95, ttft_p95) were removed
        from the 1d table because they produce inaccurate results when querying
        multiple days. In practice, services.py handles this by falling back to
        the 1h table, but the query builder itself generates raw data queries.
        """
        selects = self.builder._build_metric_selects(
            table=AnalyticsTable.INFERENCE_METRICS_1D,
            metrics=["latency_p95", "unique_users"],
            use_merge=False,
        )

        # Since 1d no longer has these columns, it falls back to raw data query
        # (services.py will actually redirect to 1h table in practice)
        assert "quantile(0.95)(response_time_ms)" in selects[0]
        assert "uniq(user_id)" in selects[1]
        # Should NOT use merge functions
        assert "quantilesTDigestMerge" not in selects[0]
        assert "uniqMerge" not in selects[1]


class TestTableSelectionEdgeCases:
    """Edge case tests for smart table selection logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.now = datetime.now()

    def test_same_day_boundary(self):
        """Test when from_date == to_date (same day)."""
        result = select_metrics_table(
            interval="1h",
            from_date=self.now,
            to_date=self.now,
        )
        # Same day means 0 day range, should use 5m rollup for short range
        assert result.table == AnalyticsTable.INFERENCE_METRICS_5M

    def test_exactly_7_day_boundary(self):
        """Test exactly 7 day boundary for table selection switch."""
        seven_days_ago = self.now - timedelta(days=7)
        result = select_metrics_table(
            interval="1h",
            from_date=seven_days_ago,
            to_date=self.now,
        )
        # 7 days is not > 7, so should still use 5m rollup
        assert result.table == AnalyticsTable.INFERENCE_METRICS_5M

    def test_just_over_7_day_boundary(self):
        """Test just over 7 day boundary switches to 1h rollup."""
        eight_days_ago = self.now - timedelta(days=8)
        result = select_metrics_table(
            interval="1h",
            from_date=eight_days_ago,
            to_date=self.now,
        )
        # 8 days > 7, should switch to 1h rollup
        assert result.table == AnalyticsTable.INFERENCE_METRICS_1H

    def test_exactly_30_day_boundary(self):
        """Test exactly 30 day boundary for daily rollup switch."""
        thirty_days_ago = self.now - timedelta(days=30)
        result = select_metrics_table(
            interval="1d",
            from_date=thirty_days_ago,
            to_date=self.now,
        )
        # 30 days is not > 30, so should still use 1h rollup
        assert result.table == AnalyticsTable.INFERENCE_METRICS_1H

    def test_just_over_30_day_boundary(self):
        """Test just over 30 day boundary switches to 1d rollup."""
        thirty_one_days_ago = self.now - timedelta(days=31)
        result = select_metrics_table(
            interval="1d",
            from_date=thirty_one_days_ago,
            to_date=self.now,
        )
        # 31 days > 30, should switch to 1d rollup
        assert result.table == AnalyticsTable.INFERENCE_METRICS_1D

    def test_otel_disabled_fallback(self):
        """Test legacy table fallback when OTel disabled."""
        os.environ["OTEL_ANALYTICS_ENABLED"] = "false"
        try:
            result = select_metrics_table(
                interval="1h",
                from_date=self.now - timedelta(days=1),
                to_date=self.now,
            )
            assert result.table == AnalyticsTable.MODEL_INFERENCE_DETAILS
            assert result.use_rollup is False
            assert "legacy" in result.reason.lower()
        finally:
            os.environ.pop("OTEL_ANALYTICS_ENABLED", None)

    def test_empty_interval_handling(self):
        """Test with empty string interval defaults to 60 minutes."""
        # Empty string should return default 60
        assert get_interval_minutes("") == 60

    def test_invalid_interval_handling(self):
        """Test with completely invalid interval values."""
        assert get_interval_minutes("xyz") == 60
        assert get_interval_minutes("100") == 60
        assert get_interval_minutes("1x") == 60

    def test_very_long_date_range(self):
        """Test with very long date range (years)."""
        three_years_ago = self.now - timedelta(days=1095)
        result = select_metrics_table(
            interval="1w",
            from_date=three_years_ago,
            to_date=self.now,
        )
        # Very long range should use 1d rollup
        assert result.table == AnalyticsTable.INFERENCE_METRICS_1D


class TestQueryBuilderEdgeCases:
    """Edge case tests for query builder."""

    def setup_method(self):
        """Set up test fixtures."""
        self.builder = OTelAnalyticsQueryBuilder()
        self.now = datetime.now()
        self.one_day_ago = self.now - timedelta(days=1)

    def test_empty_metrics_list(self):
        """Test with empty metrics list."""
        selects = self.builder._build_metric_selects(
            table=AnalyticsTable.INFERENCE_FACT,
            metrics=[],
            use_merge=False,
        )
        assert len(selects) == 0

    def test_unknown_metric_name(self):
        """Test with unsupported metric name returns empty."""
        selects = self.builder._build_metric_selects(
            table=AnalyticsTable.INFERENCE_FACT,
            metrics=["unknown_metric", "another_unknown"],
            use_merge=False,
        )
        # Unknown metrics should return empty list (no selects added)
        assert len(selects) == 0

    def test_mixed_known_unknown_metrics(self):
        """Test with mix of known and unknown metrics."""
        selects = self.builder._build_metric_selects(
            table=AnalyticsTable.INFERENCE_FACT,
            metrics=["request_count", "unknown_metric", "success_rate"],
            use_merge=False,
        )
        # Should have 2 selects (request_count and success_rate)
        assert len(selects) == 2

    def test_empty_filters(self):
        """Test with empty filters dict vs None."""
        conditions_none = self.builder._build_filter_conditions(
            table=AnalyticsTable.INFERENCE_FACT,
            from_date=self.one_day_ago,
            to_date=self.now,
            filters=None,
        )
        conditions_empty = self.builder._build_filter_conditions(
            table=AnalyticsTable.INFERENCE_FACT,
            from_date=self.one_day_ago,
            to_date=self.now,
            filters={},
        )
        # Both should have only date conditions
        assert len(conditions_none) == 2
        assert len(conditions_empty) == 2

    def test_null_filter_values(self):
        """Test with None values in filters."""
        conditions = self.builder._build_filter_conditions(
            table=AnalyticsTable.INFERENCE_FACT,
            from_date=self.one_day_ago,
            to_date=self.now,
            filters={"project": None},
        )
        # None values should not add conditions
        assert len(conditions) == 2

    def test_unmapped_column_returns_field_name(self):
        """Test that unmapped columns return the field name itself."""
        col = self.builder.get_column(AnalyticsTable.INFERENCE_FACT, "unknown_field")
        assert col == "unknown_field"


class TestSQLInjectionProtection:
    """Tests for SQL injection protection."""

    def setup_method(self):
        """Set up test fixtures."""
        self.builder = OTelAnalyticsQueryBuilder()
        self.now = datetime.now()
        self.one_day_ago = self.now - timedelta(days=1)

    def test_escape_sql_value_basic(self):
        """Test basic SQL escaping functionality."""
        assert self.builder._escape_sql_value("normal") == "normal"
        assert self.builder._escape_sql_value("it's") == "it''s"
        assert self.builder._escape_sql_value("test''double") == "test''''double"

    def test_escape_sql_value_none(self):
        """Test SQL escaping with None value."""
        assert self.builder._escape_sql_value(None) == ""

    def test_sql_injection_in_single_filter(self):
        """Test that SQL injection in single filter is escaped."""
        conditions = self.builder._build_filter_conditions(
            table=AnalyticsTable.INFERENCE_FACT,
            from_date=self.one_day_ago,
            to_date=self.now,
            filters={"project": "'; DROP TABLE InferenceFact; --"},
        )
        # The malicious value should be escaped
        assert len(conditions) == 3
        # Verify the single quote is doubled: ' becomes ''
        # Full condition: project_id = '''; DROP TABLE InferenceFact; --'
        assert "project_id = ''';" in conditions[2]
        assert "''" in conditions[2]  # Escaped quote present

    def test_sql_injection_in_list_filter(self):
        """Test that SQL injection in list filter is escaped."""
        conditions = self.builder._build_filter_conditions(
            table=AnalyticsTable.INFERENCE_FACT,
            from_date=self.one_day_ago,
            to_date=self.now,
            filters={"model": ["valid_id", "'; DELETE FROM InferenceFact; --"]},
        )
        # The malicious value should be escaped
        assert len(conditions) == 3
        assert "model_id IN" in conditions[2]
        # Verify the single quote is doubled: ' becomes ''
        # Full condition: model_id IN ('valid_id','''; DELETE FROM InferenceFact; --')
        assert "'''; DELETE FROM InferenceFact" in conditions[2]
        assert "'valid_id'" in conditions[2]  # Valid value preserved

    def test_unicode_in_filters(self):
        """Test Unicode characters in filter values."""
        conditions = self.builder._build_filter_conditions(
            table=AnalyticsTable.INFERENCE_FACT,
            from_date=self.one_day_ago,
            to_date=self.now,
            filters={"project": "日本語テスト"},
        )
        assert len(conditions) == 3
        assert "日本語テスト" in conditions[2]

    def test_special_characters_preserved(self):
        """Test that special characters (except single quotes) are preserved."""
        conditions = self.builder._build_filter_conditions(
            table=AnalyticsTable.INFERENCE_FACT,
            from_date=self.one_day_ago,
            to_date=self.now,
            filters={"project": "test@#$%^&*()"},
        )
        assert len(conditions) == 3
        assert "test@#$%^&*()" in conditions[2]


class TestDivisionByZeroProtection:
    """Tests for division by zero protection in metrics."""

    def setup_method(self):
        """Set up test fixtures."""
        self.builder = OTelAnalyticsQueryBuilder()

    def test_success_rate_rollup_has_protection(self):
        """Test success_rate has division by zero protection for rollup tables."""
        selects = self.builder._build_metric_selects(
            table=AnalyticsTable.INFERENCE_METRICS_5M,
            metrics=["success_rate"],
            use_merge=True,
        )
        assert len(selects) == 1
        assert "if(sum(request_count) > 0," in selects[0]
        assert "success_rate" in selects[0]

    def test_success_rate_fact_has_protection(self):
        """Test success_rate has division by zero protection for fact table."""
        selects = self.builder._build_metric_selects(
            table=AnalyticsTable.INFERENCE_FACT,
            metrics=["success_rate"],
            use_merge=False,
        )
        assert len(selects) == 1
        assert "if(count() > 0," in selects[0]
        assert "success_rate" in selects[0]

    def test_latency_avg_rollup_has_protection(self):
        """Test latency_avg has division by zero protection for rollup tables."""
        selects = self.builder._build_metric_selects(
            table=AnalyticsTable.INFERENCE_METRICS_5M,
            metrics=["latency_avg"],
            use_merge=True,
        )
        assert len(selects) == 1
        # Uses response_time_count (count of non-NULL latency values) for accurate average
        assert "if(sum(response_time_count) > 0," in selects[0]
        assert "latency_avg" in selects[0]

    def test_ttft_avg_rollup_has_protection(self):
        """Test ttft_avg has division by zero protection for rollup tables."""
        selects = self.builder._build_metric_selects(
            table=AnalyticsTable.INFERENCE_METRICS_5M,
            metrics=["ttft_avg"],
            use_merge=True,
        )
        assert len(selects) == 1
        # Uses ttft_count (count of non-NULL TTFT values) for accurate average
        assert "if(sum(ttft_count) > 0," in selects[0]
        assert "ttft_avg" in selects[0]


class TestQuantileIndexing:
    """Tests for correct quantile array indexing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.builder = OTelAnalyticsQueryBuilder()

    def test_latency_p50_uses_correct_index(self):
        """Test latency_p50 uses correct array index."""
        selects = self.builder._build_metric_selects(
            table=AnalyticsTable.INFERENCE_METRICS_5M,
            metrics=["latency_p50"],
            use_merge=True,
        )
        assert len(selects) == 1
        # Single-quantile merge returns single-element array, index is [1]
        assert "quantilesTDigestMerge(0.5)(response_time_quantiles)[1]" in selects[0]

    def test_latency_p95_uses_correct_index(self):
        """Test latency_p95 uses correct array index."""
        selects = self.builder._build_metric_selects(
            table=AnalyticsTable.INFERENCE_METRICS_1H,
            metrics=["latency_p95"],
            use_merge=True,
        )
        assert len(selects) == 1
        # Single-quantile merge returns single-element array, index is [1]
        assert "quantilesTDigestMerge(0.95)(response_time_quantiles)[1]" in selects[0]

    def test_latency_p99_uses_correct_index(self):
        """Test latency_p99 uses correct array index."""
        selects = self.builder._build_metric_selects(
            table=AnalyticsTable.INFERENCE_METRICS_5M,
            metrics=["latency_p99"],
            use_merge=True,
        )
        assert len(selects) == 1
        # Single-quantile merge returns single-element array, index is [1]
        assert "quantilesTDigestMerge(0.99)(response_time_quantiles)[1]" in selects[0]

    def test_ttft_p95_uses_correct_index(self):
        """Test ttft_p95 uses correct array index."""
        selects = self.builder._build_metric_selects(
            table=AnalyticsTable.INFERENCE_METRICS_5M,
            metrics=["ttft_p95"],
            use_merge=True,
        )
        assert len(selects) == 1
        # Single-quantile merge returns single-element array, index is [1]
        assert "quantilesTDigestMerge(0.95)(ttft_quantiles)[1]" in selects[0]

    def test_1d_rollup_latency_p95_fallback(self):
        """Test 1d rollup falls back to raw data query for latency_p95.

        Note: response_time_p95 column was removed from 1d table because
        pre-computed percentiles can't be accurately merged across multiple days.
        Services.py redirects these queries to 1h table for accurate results.
        """
        selects = self.builder._build_metric_selects(
            table=AnalyticsTable.INFERENCE_METRICS_1D,
            metrics=["latency_p95"],
            use_merge=False,
        )
        assert len(selects) == 1
        # Falls back to raw data query (services.py will redirect to 1h in practice)
        assert "quantile(0.95)(response_time_ms)" in selects[0]
        assert "quantilesTDigestMerge" not in selects[0]
