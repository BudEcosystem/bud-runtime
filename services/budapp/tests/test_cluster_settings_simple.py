"""Simple test to verify get_cluster_settings behavior."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_get_cluster_settings_code():
    """Verify that get_cluster_settings no longer has auto-resolution code."""

    # Read the services.py file
    services_file = os.path.join(
        os.path.dirname(__file__),
        '..', 'budapp', 'cluster_ops', 'services.py'
    )

    with open(services_file, 'r') as f:
        content = f.read()

    # Find the get_cluster_settings method
    method_start = content.find('async def get_cluster_settings(self, cluster_id: UUID) -> ClusterSettingsResponse | None:')
    if method_start == -1:
        print("❌ Could not find get_cluster_settings method")
        return False

    # Find the next method (to determine where get_cluster_settings ends)
    next_method = content.find('async def create_cluster_settings', method_start)
    if next_method == -1:
        next_method = len(content)

    # Extract the method body
    method_body = content[method_start:next_method]

    # Check that the method doesn't contain the auto-resolution code
    checks_to_avoid = [
        '_resolve_default_access_mode',
        'resolved_access_mode',
        'update_one(db_settings)',
        'Failed to persist inferred access mode'
    ]

    print("Checking get_cluster_settings method...")
    print("-" * 50)

    issues_found = []
    for check in checks_to_avoid:
        if check in method_body:
            issues_found.append(check)
            print(f"❌ Found unwanted code: '{check}'")

    # Check that the method is simple (just gets from DB and returns)
    expected_patterns = [
        'ClusterSettingsDataManager(self.session)',
        'get_cluster_settings(cluster_id)',
        'if not db_settings:',
        'return None',
        'return ClusterSettingsResponse.model_validate(db_settings)'
    ]

    for pattern in expected_patterns:
        if pattern in method_body:
            print(f"✓ Found expected pattern: '{pattern}'")
        else:
            print(f"⚠️ Missing expected pattern: '{pattern}'")

    print("-" * 50)

    if issues_found:
        print(f"\n❌ Test FAILED: Found auto-resolution code in get_cluster_settings")
        print(f"   Issues: {', '.join(issues_found)}")
        return False
    else:
        print("\n✅ Test PASSED: get_cluster_settings is now a simple getter")
        print("   - No auto-resolution of access_mode")
        print("   - Returns data from DB as-is")
        print("   - Returns None for access_mode if not set by user")
        return True


def verify_create_update_methods_still_have_resolution():
    """Verify that create/update/upsert methods still have resolution logic."""

    services_file = os.path.join(
        os.path.dirname(__file__),
        '..', 'budapp', 'cluster_ops', 'services.py'
    )

    with open(services_file, 'r') as f:
        content = f.read()

    methods_to_check = [
        'create_cluster_settings',
        'update_cluster_settings',
        'upsert_cluster_settings'
    ]

    print("\nVerifying create/update/upsert methods still have resolution...")
    print("-" * 50)

    all_good = True
    for method_name in methods_to_check:
        # Find the method
        method_start = content.find(f'async def {method_name}(')
        if method_start == -1:
            print(f"⚠️ Could not find {method_name} method")
            continue

        # Find next method
        next_method_idx = content.find('\n    async def ', method_start + 10)
        if next_method_idx == -1:
            next_method_idx = content.find('\n    def ', method_start + 10)
        if next_method_idx == -1:
            next_method_idx = len(content)

        method_body = content[method_start:next_method_idx]

        # Check for resolution logic
        if '_resolve_default_access_mode' in method_body:
            print(f"✓ {method_name}: Still has access mode resolution")
        else:
            print(f"❌ {method_name}: Missing resolution logic!")
            all_good = False

    print("-" * 50)

    if all_good:
        print("\n✅ All create/update/upsert methods correctly have resolution logic")
    else:
        print("\n❌ Some methods are missing resolution logic")

    return all_good


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Cluster Settings Behavior")
    print("=" * 60)

    test1_result = test_get_cluster_settings_code()
    test2_result = verify_create_update_methods_still_have_resolution()

    print("\n" + "=" * 60)
    if test1_result and test2_result:
        print("✅ ALL TESTS PASSED!")
        print("\nSummary:")
        print("- get_cluster_settings: Returns DB values as-is (no auto-resolution)")
        print("- create/update/upsert: Still resolve access_mode when needed")
        print("- If user didn't set access_mode, get returns None")
    else:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
