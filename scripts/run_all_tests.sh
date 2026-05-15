#!/bin/bash
#
# Comprehensive test runner for Voyager Travel Agent
# Runs backend unit tests, integration tests, API tests, and frontend component tests
# Generates coverage reports for all test suites
#

set -e  # Exit on error

echo "======================================"
echo "🧪 Voyager Travel Agent - Test Suite"
echo "======================================"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create coverage directory
mkdir -p coverage_report

# ====================================
# 1. Backend Unit Tests
# ====================================
echo -e "${BLUE}📦 Running Backend Unit Tests...${NC}"
echo ""

pytest tests/unit -v \
    --cov=agents \
    --cov=graph \
    --cov=config \
    --cov-report=term-missing \
    --cov-report=html:coverage_report/backend_unit_html \
    --cov-report=json:coverage_report/backend_unit.json

echo ""
echo -e "${GREEN}✅ Backend Unit Tests Complete${NC}"
echo ""

# ====================================
# 2. Backend Integration Tests
# ====================================
echo -e "${BLUE}🔗 Running Backend Integration Tests...${NC}"
echo ""

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo -e "${YELLOW}⚠️  ANTHROPIC_API_KEY not set - skipping integration tests${NC}"
    echo ""
else
    pytest tests/integration -v \
        --cov=api \
        --cov=graph \
        --cov-append \
        --cov-report=term-missing \
        --cov-report=html:coverage_report/backend_integration_html \
        --cov-report=json:coverage_report/backend_integration.json

    echo ""
    echo -e "${GREEN}✅ Backend Integration Tests Complete${NC}"
    echo ""
fi

# ====================================
# 3. Frontend Tests
# ====================================
echo -e "${BLUE}⚛️  Running Frontend Tests...${NC}"
echo ""

cd frontend

# Install dependencies if not installed
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Run tests with coverage
npm run test:coverage

echo ""
echo -e "${GREEN}✅ Frontend Tests Complete${NC}"
echo ""

cd ..

# ====================================
# 4. Generate Combined Coverage Report
# ====================================
echo -e "${BLUE}📊 Generating Coverage Summary...${NC}"
echo ""

# Backend coverage summary
echo "📦 Backend Coverage:"
pytest tests/ --cov=agents --cov=graph --cov=api --cov=config --cov-report=term --no-header -q 2>&1 | grep -A 10 "TOTAL"

echo ""

# Frontend coverage summary
echo "⚛️  Frontend Coverage:"
if [ -f "frontend/coverage/coverage-summary.json" ]; then
    cat frontend/coverage/coverage-summary.json | grep -o '"total":{"lines":{"pct":[0-9.]*}' | grep -o '[0-9.]*'
else
    echo "Frontend coverage report not found"
fi

echo ""
echo "======================================"
echo -e "${GREEN}🎉 All Tests Complete!${NC}"
echo "======================================"
echo ""
echo "Coverage reports:"
echo "  Backend Unit:        coverage_report/backend_unit_html/index.html"
echo "  Backend Integration: coverage_report/backend_integration_html/index.html"
echo "  Frontend:            frontend/coverage/index.html"
echo ""
