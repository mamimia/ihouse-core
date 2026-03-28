#!/bin/bash

# Sync docs to NotebookLM
# Note: You need to authenticate first using `uvx --from notebooklm-mcp-cli nlm login`
# and identify your Notebook ID with `uvx --from notebooklm-mcp-cli nlm notebook list`

if [ -z "$1" ]; then
  echo "Usage: scripts/sync_docs_to_notebooklm.sh <notebook_id>"
  echo "Example: scripts/sync_docs_to_notebooklm.sh 12345abc"
  exit 1
fi

NOTEBOOK_ID=$1

echo "Syncing markdown files from docs/ to NotebookLM..."

# Requires uv to be installed
if ! command -v uvx &> /dev/null; then
  echo "Error: uvx is not installed. Please install uv."
  exit 1
fi

find docs -type f -name "*.md" | while read -r file; do
    echo "Uploading $file..."
    uvx --from notebooklm-mcp-cli nlm source add "$NOTEBOOK_ID" "$file" || echo "Failed to add $file"
done

echo "Sync complete!"
