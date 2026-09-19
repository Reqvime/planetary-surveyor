[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SaveDirectory,

    [string]$BackupRoot = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'NMS-Save-Backups')
)

$ErrorActionPreference = 'Stop'

if (Get-Process -Name 'NMS' -ErrorAction SilentlyContinue) {
    throw 'No Man''s Sky is running. Close the game normally before creating a backup.'
}

$resolvedSave = (Resolve-Path -LiteralPath $SaveDirectory).Path
if (-not (Test-Path -LiteralPath $resolvedSave -PathType Container)) {
    throw "Save directory was not found: $SaveDirectory"
}

New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$destination = Join-Path $BackupRoot ((Split-Path -Leaf $resolvedSave) + '-' + $timestamp)

if (Test-Path -LiteralPath $destination) {
    throw "Backup destination already exists: $destination"
}

Copy-Item -LiteralPath $resolvedSave -Destination $destination -Recurse

$sourceStats = Get-ChildItem -LiteralPath $resolvedSave -File -Recurse |
    Measure-Object -Property Length -Sum
$backupStats = Get-ChildItem -LiteralPath $destination -File -Recurse |
    Measure-Object -Property Length -Sum

if ($sourceStats.Count -ne $backupStats.Count -or $sourceStats.Sum -ne $backupStats.Sum) {
    throw 'Backup file count or total size does not match the source directory.'
}

[pscustomobject]@{
    BackupPath = $destination
    FileCount = $backupStats.Count
    TotalBytes = $backupStats.Sum
}
