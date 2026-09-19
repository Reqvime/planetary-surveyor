[CmdletBinding()]
param(
    [string]$GameRoot = ''
)

$ErrorActionPreference = 'Stop'
if (-not $GameRoot) {
    $GameRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
}
$nmsExe = Join-Path $GameRoot 'Binaries\NMS.exe'

if (-not (Test-Path -LiteralPath $nmsExe -PathType Leaf)) {
    throw "NMS.exe was not found: $nmsExe"
}

if (-not ('ReadOnlyNmsPatternScanner' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;

public static class ReadOnlyNmsPatternScanner
{
    public static long[] FindAll(string filePath, string patternText)
    {
        byte[] data = File.ReadAllBytes(filePath);
        string[] tokens = patternText.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
        int[] pattern = new int[tokens.Length];
        int anchor = -1;

        for (int i = 0; i < tokens.Length; i++)
        {
            if (tokens[i] == "?" || tokens[i] == "??")
            {
                pattern[i] = -1;
            }
            else
            {
                pattern[i] = byte.Parse(tokens[i], NumberStyles.HexNumber, CultureInfo.InvariantCulture);
                if (anchor < 0) anchor = i;
            }
        }

        var hits = new List<long>();
        int limit = data.Length - pattern.Length;
        for (int offset = 0; offset <= limit; offset++)
        {
            if (anchor >= 0 && data[offset + anchor] != pattern[anchor]) continue;

            bool match = true;
            for (int j = 0; j < pattern.Length; j++)
            {
                if (pattern[j] >= 0 && data[offset + j] != pattern[j])
                {
                    match = false;
                    break;
                }
            }

            if (match) hits.Add(offset);
        }

        return hits.ToArray();
    }
}
'@
}

$patterns = [ordered]@{
    PopulateDiscoveryInfo = '48 8B C4 4C 89 48 ? 44 89 40 ? 48 89 48'
    SubmitDiscoveryDataLegacy = '48 89 5C 24 ? 48 89 74 24 ? 57 48 83 EC ? 48 8B 59 ? 49 8B F8 48 8B F2'
    SubmitDiscoveryPipelineV70Candidate = (@(
        '4C 89 4C 24 ? 44 89 44 24 ? 48 89 4C 24 ? 55 53 41 55 41 56'
        '48 8D AC 24 ? ? ? ? 48 81 EC ? ? ? ? 48 8B D9 4C 8B F2 8B 4A ?'
        'E8 ? ? ? ? 84 C0 75 ?'
    ) -join ' ')
    UpdateScannableMarkers = (@(
        '48 89 4C 24 ? 55 53 57 41 54 41 57 48 8D AC 24 ? ? ? ?'
        'B8 ? ? ? ? E8 ? ? ? ? 48 2B E0 0F 29 B4 24'
    ) -join ' ')
    ScannableComponentUpdate = (@(
        '48 89 5C 24 ? 55 56 57 48 81 EC ? ? ? ? 48 8B 41 30'
        '48 8B F9 F6 40 08 01 0F 84 ? ? ? ? 48 8B 59 28 80 7B 77 04'
    ) -join ' ')
    ResolveDiscoveryDataFromSceneNode = (@(
        '48 89 5C 24 ? 48 89 74 24 ? 48 89 7C 24 ? 55 41 54 41 55 41 56 41 57'
        '48 8D 6C 24 ? 48 81 EC ? ? ? ? 48 8D 45 ? 4C 8B EA'
    ) -join ' ')
    GetNodeAbsoluteTransform = '40 56 48 83 EC ? 44 8B C9 49 8B F0 41 C1 E9 ? 45 85 C9'
    IsDiscoveryKnown = (@(
        '48 83 EC 28 48 8B 0D ? ? ? ? 48 81 C1 ? ? ? ? E8 ? ? ? ?'
        '48 85 C0 74 ? F6 80 ? ? ? ? ? 75 ? B0 01'
    ) -join ' ')
    PostSubmitDiscovery = (@(
        '48 89 5C 24 ? 48 89 74 24 ? 48 89 7C 24 ? 55 41 54 41 55 41 56 41 57'
        '48 8D AC 24 C0 C1 FF FF B8 40 3F 00 00 E8 ? ? ? ? 48 2B E0'
        '48 8B 1D ? ? ? ? 45 33 F6'
    ) -join ' ')
    GameTime64 = '33 C9 48 FF 25 ? ? ? ? CC CC CC CC CC CC CC 48 81 EC'
    NmsPyInternalUpdate = '48 89 5C 24 ? 57 48 83 EC ? 48 8B 05 ? ? ? ? 48 8B D9 0F 29 74 24'
    NmsPyInternalFsmStateChange = '48 89 6C 24 ? 48 89 74 24 ? 57 48 83 EC ? 4C 8B 51 ? 49 8B E8'
    NmsPyInternalStateChange = '4C 8B 51 ? 4D 8B D8 48 8B 05'
}

$exeItem = Get-Item -LiteralPath $nmsExe
$signatureResults = foreach ($entry in $patterns.GetEnumerator()) {
    $hits = [ReadOnlyNmsPatternScanner]::FindAll($nmsExe, $entry.Value)
    [pscustomobject]@{
        Hook = $entry.Key
        MatchCount = $hits.Count
        FileOffsets = @($hits | ForEach-Object { '0x{0:X}' -f $_ })
    }
}

$pythonList = try {
    (& py -0p 2>&1 | Out-String).TrimEnd()
}
catch {
    $_.Exception.Message
}

[pscustomobject]@{
    NmsExe = $exeItem.FullName
    FileVersion = $exeItem.VersionInfo.FileVersion
    ProductVersion = $exeItem.VersionInfo.ProductVersion
    PythonInstallations = $pythonList
    Signatures = @($signatureResults)
}
