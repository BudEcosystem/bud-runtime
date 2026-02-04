#!/bin/bash
#
# Run Auth Flow E2E Tests
#
# Usage:
#   ./run_auth_tests.sh              # Run all auth tests
#   ./run_auth_tests.sh p0           # Run only P0 (critical) tests
#   ./run_auth_tests.sh p1           # Run only P1 (important) tests
#   ./run_auth_tests.sh login        # Run only login tests
#   ./run_auth_tests.sh all          # Run all auth tests with verbose output

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Auth Flow E2E Tests${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if .env.e2e exists
if [ ! -f ".env.e2e" ]; then
    echo -e "${YELLOW}Warning: .env.e2e not found. Copying from .env.e2e.sample${NC}"
    if [ -f ".env.e2e.sample" ]; then
        cp .env.e2e.sample .env.e2e
        echo -e "${GREEN}Created .env.e2e from sample${NC}"
    else
        echo -e "${RED}Error: .env.e2e.sample not found${NC}"
        exit 1
    fi
fi

# Create reports directory
mkdir -p reports

# Parse arguments
TEST_FILTER=""
PYTEST_ARGS=""

case "$1" in
    "p0")
        echo -e "${YELLOW}Running P0 (Critical) auth tests only${NC}"
        TEST_FILTER="-m 'auth and priority_p0'"
        ;;
    "p1")
        echo -e "${YELLOW}Running P1 (Important) auth tests only${NC}"
        TEST_FILTER="-m 'auth and priority_p1'"
        ;;
    "login")
        echo -e "${YELLOW}Running login tests only${NC}"
        TEST_FILTER="flows/auth/test_login.py"
        ;;
    "logout")
        echo -e "${YELLOW}Running logout tests only${NC}"
        TEST_FILTER="flows/auth/test_logout.py"
        ;;
    "refresh")
        echo -e "${YELLOW}Running token refresh tests only${NC}"
        TEST_FILTER="flows/auth/test_token_refresh.py"
        ;;
    "register")
        echo -e "${YELLOW}Running registration tests only${NC}"
        TEST_FILTER="flows/auth/test_registration.py"
        ;;
    "reset")
        echo -e "${YELLOW}Running password reset tests only${NC}"
        TEST_FILTER="flows/auth/test_password_reset.py"
        ;;
    "protected")
        echo -e "${YELLOW}Running protected endpoint tests only${NC}"
        TEST_FILTER="flows/auth/test_protected_endpoints.py"
        ;;
    "all"|"")
        echo -e "${YELLOW}Running all auth tests${NC}"
        TEST_FILTER="flows/auth/"
        ;;
    *)
        echo -e "${RED}Unknown option: $1${NC}"
        echo "Usage: $0 [p0|p1|login|logout|refresh|register|reset|protected|all]"
        exit 1
        ;;
esac

echo ""

# Run pytest
echo -e "${GREEN}Starting tests...${NC}"
echo ""

# Build pytest command
PYTEST_CMD="python -m pytest"
PYTEST_CMD="$PYTEST_CMD $TEST_FILTER"
PYTEST_CMD="$PYTEST_CMD -v"
PYTEST_CMD="$PYTEST_CMD --tb=short"
PYTEST_CMD="$PYTEST_CMD --html=reports/auth-e2e-report.html"
PYTEST_CMD="$PYTEST_CMD --self-contained-html"
PYTEST_CMD="$PYTEST_CMD --timeout=60"
PYTEST_CMD="$PYTEST_CMD -x"  # Stop on first failure

echo "Running: $PYTEST_CMD"
echo ""

eval $PYTEST_CMD

TEST_EXIT_CODE=$?

echo ""
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  All tests passed!${NC}"
    echo -e "${GREEN}========================================${NC}"
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}  Some tests failed!${NC}"
    echo -e "${RED}========================================${NC}"
fi

echo ""
echo "HTML report: reports/auth-e2e-report.html"
echo "Log file: reports/e2e-tests.log"

exit $TEST_EXIT_CODE
