#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""Tests for gateway blocking rules functionality."""

import pytest
from uuid import uuid4

from budapp.commons.constants import BlockingRuleType, BlockingRuleStatus
from budapp.metric_ops.crud import BlockingRuleDataManager
from budapp.metric_ops.schemas import BlockingRuleCreate, BlockingRuleUpdate
from budapp.metric_ops.services import BlockingRulesService


@pytest.mark.asyncio
async def test_create_ip_blocking_rule(db_session, test_user, test_project):
    """Test creating an IP blocking rule."""
    service = BlockingRulesService(db_session, test_user)

    rule_data = BlockingRuleCreate(
        name="Block suspicious IPs",
        description="Block IPs that have been flagged as suspicious",
        rule_type=BlockingRuleType.IP_BLOCKING,
        rule_config={"ip_addresses": ["192.168.1.100", "10.0.0.0/24"]},
        reason="Multiple failed authentication attempts",
        priority=10,
    )

    rule = await service.create_blocking_rule(test_project.id, rule_data)

    assert rule.name == "Block suspicious IPs"
    assert rule.rule_type == BlockingRuleType.IP_BLOCKING
    assert rule.status == BlockingRuleStatus.ACTIVE
    assert rule.project_id == test_project.id
    assert rule.created_by == test_user.id
    assert "192.168.1.100" in rule.rule_config["ip_addresses"]


@pytest.mark.asyncio
async def test_create_country_blocking_rule(db_session, test_user, test_project):
    """Test creating a country blocking rule."""
    service = BlockingRulesService(db_session, test_user)

    rule_data = BlockingRuleCreate(
        name="Block high-risk countries",
        description="Block traffic from countries with high fraud rates",
        rule_type=BlockingRuleType.COUNTRY_BLOCKING,
        rule_config={"countries": ["CN", "RU", "KP"]},
        reason="Compliance requirement",
        priority=20,
    )

    rule = await service.create_blocking_rule(test_project.id, rule_data)

    assert rule.rule_type == BlockingRuleType.COUNTRY_BLOCKING
    assert "CN" in rule.rule_config["countries"]


@pytest.mark.asyncio
async def test_create_user_agent_blocking_rule(db_session, test_user, test_project):
    """Test creating a user agent blocking rule."""
    service = BlockingRulesService(db_session, test_user)

    rule_data = BlockingRuleCreate(
        name="Block bots and crawlers",
        rule_type=BlockingRuleType.USER_AGENT_BLOCKING,
        rule_config={"patterns": ["bot", "crawler", "spider", "scraper"]},
        priority=5,
    )

    rule = await service.create_blocking_rule(test_project.id, rule_data)

    assert rule.rule_type == BlockingRuleType.USER_AGENT_BLOCKING
    assert "bot" in rule.rule_config["patterns"]


@pytest.mark.asyncio
async def test_create_rate_based_blocking_rule(db_session, test_user, test_project):
    """Test creating a rate-based blocking rule."""
    service = BlockingRulesService(db_session, test_user)

    rule_data = BlockingRuleCreate(
        name="Rate limit excessive requests",
        rule_type=BlockingRuleType.RATE_BASED_BLOCKING,
        rule_config={
            "threshold": 100,
            "window_seconds": 60,
            "action": "block",
        },
        priority=30,
    )

    rule = await service.create_blocking_rule(test_project.id, rule_data)

    assert rule.rule_type == BlockingRuleType.RATE_BASED_BLOCKING
    assert rule.rule_config["threshold"] == 100
    assert rule.rule_config["window_seconds"] == 60


@pytest.mark.asyncio
async def test_list_blocking_rules(db_session, test_user, test_project):
    """Test listing blocking rules with filters."""
    service = BlockingRulesService(db_session, test_user)

    # Create multiple rules
    rules = []
    for i in range(3):
        rule_data = BlockingRuleCreate(
            name=f"Test rule {i}",
            rule_type=BlockingRuleType.IP_BLOCKING,
            rule_config={"ip_addresses": [f"192.168.1.{i}"]},
            priority=i,
        )
        rule = await service.create_blocking_rule(test_project.id, rule_data)
        rules.append(rule)

    # List all rules
    response = await service.list_blocking_rules()
    assert response.total >= 3

    # Filter by project
    response = await service.list_blocking_rules(project_id=test_project.id)
    assert all(r.project_id == test_project.id for r in response.items)

    # Filter by rule type
    response = await service.list_blocking_rules(rule_type=BlockingRuleType.IP_BLOCKING)
    assert all(r.rule_type == BlockingRuleType.IP_BLOCKING for r in response.items)


@pytest.mark.asyncio
async def test_update_blocking_rule(db_session, test_user, test_project):
    """Test updating a blocking rule."""
    service = BlockingRulesService(db_session, test_user)

    # Create a rule
    rule_data = BlockingRuleCreate(
        name="Original name",
        rule_type=BlockingRuleType.IP_BLOCKING,
        rule_config={"ip_addresses": ["192.168.1.1"]},
    )
    rule = await service.create_blocking_rule(test_project.id, rule_data)

    # Update the rule
    update_data = BlockingRuleUpdate(
        name="Updated name",
        status=BlockingRuleStatus.INACTIVE,
        rule_config={"ip_addresses": ["192.168.1.1", "192.168.1.2"]},
    )
    updated_rule = await service.update_blocking_rule(rule.id, update_data)

    assert updated_rule.name == "Updated name"
    assert updated_rule.status == BlockingRuleStatus.INACTIVE
    assert len(updated_rule.rule_config["ip_addresses"]) == 2


@pytest.mark.asyncio
async def test_delete_blocking_rule(db_session, test_user, test_project):
    """Test deleting a blocking rule."""
    service = BlockingRulesService(db_session, test_user)

    # Create a rule
    rule_data = BlockingRuleCreate(
        name="To be deleted",
        rule_type=BlockingRuleType.IP_BLOCKING,
        rule_config={"ip_addresses": ["192.168.1.1"]},
    )
    rule = await service.create_blocking_rule(test_project.id, rule_data)

    # Delete the rule
    deleted = await service.delete_blocking_rule(rule.id)
    assert deleted is True

    # Verify it's deleted
    with pytest.raises(Exception):  # Should raise not found exception
        await service.get_blocking_rule(rule.id)


@pytest.mark.asyncio
async def test_validate_rule_config(db_session, test_user, test_project):
    """Test rule configuration validation."""
    service = BlockingRulesService(db_session, test_user)

    # Test invalid IP blocking config
    with pytest.raises(Exception):
        rule_data = BlockingRuleCreate(
            name="Invalid IP rule",
            rule_type=BlockingRuleType.IP_BLOCKING,
            rule_config={},  # Missing ip_addresses
        )
        await service.create_blocking_rule(test_project.id, rule_data)

    # Test invalid rate-based config
    with pytest.raises(Exception):
        rule_data = BlockingRuleCreate(
            name="Invalid rate rule",
            rule_type=BlockingRuleType.RATE_BASED_BLOCKING,
            rule_config={"threshold": 100},  # Missing window_seconds
        )
        await service.create_blocking_rule(test_project.id, rule_data)


@pytest.mark.asyncio
async def test_rule_name_uniqueness(db_session, test_user, test_project):
    """Test that rule names must be unique within a project."""
    service = BlockingRulesService(db_session, test_user)

    # Create first rule
    rule_data = BlockingRuleCreate(
        name="Unique name",
        rule_type=BlockingRuleType.IP_BLOCKING,
        rule_config={"ip_addresses": ["192.168.1.1"]},
    )
    await service.create_blocking_rule(test_project.id, rule_data)

    # Try to create another rule with the same name
    with pytest.raises(Exception):  # Should raise conflict exception
        await service.create_blocking_rule(test_project.id, rule_data)


@pytest.mark.asyncio
async def test_auto_blocking_rule_creation(db_session, test_user, test_project):
    """Test automatic blocking rule creation."""
    service = BlockingRulesService(db_session, test_user)

    rule = await service.create_auto_blocking_rule(
        project_id=test_project.id,
        ip_address="192.168.1.100",
        reason="Exceeded error threshold: 50 errors in 60 minutes",
        duration_minutes=1440,
    )

    assert rule.name == "Auto-block: 192.168.1.100"
    assert rule.rule_type == BlockingRuleType.IP_BLOCKING
    assert rule.priority == 100  # High priority for auto-blocks
    assert "192.168.1.100" in rule.rule_config["ip_addresses"]
