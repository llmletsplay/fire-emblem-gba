#!/bin/bash

# Clean Run Script - Deletes all runtime data for a fresh start
# Usage: ./scripts/unix/clean-run.sh

# Exit on undefined variables, but handle errors manually for better UX
set -u

echo "=== Fire Emblem AI Run Cleanup ==="
echo "This will delete all runtime data including saves, logs, and session history."
echo ""

# Confirm before proceeding
read -p "Are you sure you want to continue? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo "Cleaning up runtime data..."
echo ""

# Counter for deleted items
DELETED_COUNT=0

# Function to safely delete files/directories and count
delete_file() {
    if [ -e "$1" ]; then
        rm -rf "$1"
        echo "  ✓ Deleted: $1"
        DELETED_COUNT=$((DELETED_COUNT + 1))
        return 0
    fi
    return 1
}

# Function to delete all contents of a directory
delete_dir_contents() {
    if [ -d "$1" ]; then
        local count
        count=$(find "$1" -type f 2>/dev/null | wc -l | tr -d ' ')
        # Delete all files and subdirectories
        find "$1" -mindepth 1 -delete 2>/dev/null || true
        echo "  ✓ Cleared: $1 ($count files)"
        DELETED_COUNT=$((DELETED_COUNT + 1))
        return 0
    fi
    return 1
}

# Function to delete matching files by pattern in current directory
delete_pattern() {
    local pattern="$1"
    local found=0
    for file in $pattern; do
        if [ -e "$file" ]; then
            rm -f "$file"
            found=1
        fi
    done
    if [ $found -eq 1 ]; then
        echo "  ✓ Deleted: $pattern"
        DELETED_COUNT=$((DELETED_COUNT + 1))
    fi
}

echo "1. Cleaning generated knowledge and state files..."
delete_file "fe_knowledge.json"
delete_file "state.json"
delete_file ".llm_provider_result"
delete_file "websocket.sock"
delete_file "mgba.sock"

echo ""
echo "2. Cleaning log files..."
delete_dir_contents "logs"

echo ""
echo "3. Cleaning session and chronicle data..."
delete_dir_contents "fe-client/public/chronicle"
delete_dir_contents "assets/chronicle"

echo ""
echo "4. Cleaning screenshot files..."
delete_dir_contents "screenshots"
delete_file "latest.png"
delete_file "minimap.png"
delete_pattern "screenshot_*.png"

echo ""
echo "5. Cleaning build artifacts..."
delete_dir_contents "fe-client/dist"
delete_dir_contents "fe-web/dist"

echo ""
echo "6. Cleaning checkpoint data..."
delete_dir_contents "checkpoints"

echo ""
echo "7. Cleaning temporary files..."
if [ -d "tmp" ]; then
    # Delete files in tmp root
    find tmp -maxdepth 1 -type f -delete 2>/dev/null || true
    # Delete generated temporary directories
    find tmp -mindepth 1 -maxdepth 1 -type d -exec rm -rf {} + 2>/dev/null || true
    echo "  ✓ Cleaned: tmp/"
    DELETED_COUNT=$((DELETED_COUNT + 1))
fi

echo ""
echo "8. Cleaning Python cache..."
PYTHON_CACHE_DELETED=0
# Find and delete __pycache__ directories
while IFS= read -r -d '' dir; do
    rm -rf "$dir"
    PYTHON_CACHE_DELETED=1
done < <(find . -type d -name "__pycache__" -print0 2>/dev/null) || true

# Delete .pyc and .pyo files
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true

if [ $PYTHON_CACHE_DELETED -eq 1 ]; then
    echo "  ✓ Cleaned Python cache files"
    DELETED_COUNT=$((DELETED_COUNT + 1))
fi

echo ""
echo "9. Cleaning game saves and save states..."
delete_pattern "roms/*.sav"
delete_pattern "roms/*.ss*"

echo ""
echo "=== Cleanup Complete ==="
echo "Deleted/cleared $DELETED_COUNT items"
echo ""
echo "Note: ROM files (.gba) were preserved."
echo "To start fresh, run: ./start.sh"
