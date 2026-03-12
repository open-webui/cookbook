# Context Data Directory

This directory contains all the knowledge collections that will be synced to OpenWebUI.

## Structure

Each subdirectory represents a knowledge collection. The name of the directory will be converted to a collection name (e.g., `sample-collection` becomes "Sample Collection").

## Adding Content

To add new content:

1. Create a new subdirectory for your collection if it doesn't exist
2. Add your files to the subdirectory
3. Commit and push your changes

The GitHub workflow will automatically sync your changes to OpenWebUI.

## Supported File Types

The following file types are supported:
- Text files (.txt)
- Markdown files (.md)
- PDF files (.pdf)
- Word documents (.docx)
- Excel spreadsheets (.xlsx)
- PowerPoint presentations (.pptx)
- CSV files (.csv)
- JSON files (.json)
- HTML files (.html)

## Example

```
context-data/
├── company-policies/
│   ├── vacation-policy.pdf
│   └── code-of-conduct.md
├── product-documentation/
│   ├── user-manual.md
│   └── api-reference.json
└── training-materials/
    ├── onboarding.pptx
    └── sales-training.pdf
```

This structure will create three knowledge collections in OpenWebUI:
1. "Company Policies"
2. "Product Documentation"
3. "Training Materials"
