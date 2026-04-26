# Download CSL Files Spec

## Why

The paper-toolkit-mcp project requires specific CSL (Citation Style Language) files for citation formatting. These files need to be downloaded from their official GitHub repositories and saved locally for use by the application.

## What Changes

- **Download** 5 specific CSL files from GitHub repositories
- **Create** `csl/` directory if it doesn't exist
- **Save** files to `d:\Codes\paper-toolkit-mcp\csl\`

## Impact

- **Affected directories**: `d:\Codes\paper-toolkit-mcp\csl\` (new)
- **Affected files**: 
  - `csl/chinese-gb7714-2015-numeric.csl` (new)
  - `csl/apa.csl` (new)
  - `csl/ieee.csl` (new)
  - `csl/vancouver.csl` (new)
  - `csl/harvard-cite-them-right.csl` (new)

## ADDED Requirements

### Requirement: CSL File Download
The system shall download the following 5 CSL files and save them to `d:\Codes\paper-toolkit-mcp\csl\`:

1. chinese-gb7714-2015-numeric.csl
2. apa.csl
3. ieee.csl
4. vancouver.csl
5. harvard-cite-them-right.csl

#### Scenario: Successful Download
- **WHEN** a valid GitHub raw URL is provided
- **THEN** the file content is downloaded and saved to the correct directory

#### Scenario: URL Fallback
- **WHEN** the primary URL returns 404 or fails
- **THEN** try alternative URLs from the specified repositories
- **AND** download from the first successful alternative

#### Scenario: Directory Creation
- **WHEN** the `csl/` directory doesn't exist
- **THEN** create it before downloading files
