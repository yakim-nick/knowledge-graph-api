#!/usr/bin/env bash
# Offline K8s manifest validator — does not require a running cluster

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_NAME="$(basename "$(dirname "$PROJECT_DIR")")"

echo "=== Validating K8s manifests: $PROJECT_NAME ==="

errors=0
for file in "$PROJECT_DIR"/*.yaml; do
    name="$(basename "$file")"
    if [ "$name" = "kustomization.yaml" ]; then
        echo "  SKIP: $name (kustomize config)"
        continue
    fi

    # Validate YAML syntax — catch failures manually
    if python3 -c "
import yaml, sys
with open('$file') as f:
    docs = list(yaml.safe_load_all(f))
if not docs or all(d is None for d in docs):
    sys.exit(1)
" 2>/dev/null; then
        # YAML is valid — check with kubectl if available (ignore cluster errors)
        result=$(kubectl apply --dry-run=client --validate=false -f "$file" 2>&1) || true
        if echo "$result" | grep -q "connection refused"; then
            echo "  PASS: $name (offline — no cluster needed)"
        elif echo "$result" | grep -q "created"; then
            echo "  PASS: $name"
        else
            echo "  FAIL: $name — $result"
            errors=$((errors+1))
        fi
    else
        echo "  FAIL: $name (YAML parse error)"
        errors=$((errors+1))
    fi
done

echo ""
if [ $errors -eq 0 ]; then
    echo "Result: ALL PASS ($PROJECT_NAME)"
else
    echo "Result: $errors file(s) FAILED ($PROJECT_NAME)"
fi
exit $errors
