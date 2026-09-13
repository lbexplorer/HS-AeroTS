[CmdletBinding()]
param(
    [switch]$OrganizeOnly
)

$ErrorActionPreference = 'Stop'

$PaperDirectory = $PSScriptRoot
$BuildDirectory = Join-Path $PaperDirectory 'build'
$TemporaryOutputDirectory = Join-Path $BuildDirectory 'latex-temp\main'
$LegacyOutputDirectory = Join-Path $BuildDirectory 'latex-temp\legacy-top-level'
$PackageDirectory = Join-Path $BuildDirectory 'packages'
$ArchiveDirectory = Join-Path $BuildDirectory 'archive'

function Move-TopLevelNonPdfFiles {
    New-Item -ItemType Directory -Force -Path $LegacyOutputDirectory, $PackageDirectory, $ArchiveDirectory | Out-Null

    Get-ChildItem -LiteralPath $BuildDirectory -File | ForEach-Object {
        $DestinationDirectory = if ($_.Extension -ieq '.zip') {
            $PackageDirectory
        }
        elseif ($_.Extension -ieq '.pdf' -and $_.BaseName -ne 'main') {
            return
        }
        elseif ($_.Extension -ieq '.pdf') {
            $ArchiveDirectory
        }
        else {
            $LegacyOutputDirectory
        }

        Move-Item -LiteralPath $_.FullName -Destination $DestinationDirectory -Force
    }
}

New-Item -ItemType Directory -Force -Path $BuildDirectory | Out-Null
Move-TopLevelNonPdfFiles

if ($OrganizeOnly) {
    Write-Host "Organized non-PDF build artifacts under $BuildDirectory"
    exit 0
}

$ReleasePattern = '^HS-AeroTS_Drones_revision_v(?<major>\d+)\.(?<minor>\d+)\.pdf$'
$LatestVersion = Get-ChildItem -LiteralPath $BuildDirectory -File -Filter '*.pdf' |
    ForEach-Object {
        if ($_.Name -match $ReleasePattern) {
            [PSCustomObject]@{
                Major = [int]$Matches.major
                Minor = [int]$Matches.minor
            }
        }
    } |
    Sort-Object Major, Minor -Descending |
    Select-Object -First 1

if ($null -eq $LatestVersion) {
    $NextMajor = 1
    $NextMinor = 0
}
else {
    $NextMajor = $LatestVersion.Major
    $NextMinor = $LatestVersion.Minor + 1
}

$ReleaseName = "HS-AeroTS_Drones_revision_v$NextMajor.$NextMinor.pdf"
$ReleasePath = Join-Path $BuildDirectory $ReleaseName

New-Item -ItemType Directory -Force -Path $TemporaryOutputDirectory | Out-Null
Push-Location $PaperDirectory
try {
    & latexmk -pdf -g "-outdir=$TemporaryOutputDirectory" -jobname=main -interaction=nonstopmode -halt-on-error main.tex
    if ($LASTEXITCODE -ne 0) {
        throw "latexmk failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

$CompiledPdf = Join-Path $TemporaryOutputDirectory 'main.pdf'
if (-not (Test-Path -LiteralPath $CompiledPdf)) {
    throw "latexmk completed without producing $CompiledPdf."
}

Copy-Item -LiteralPath $CompiledPdf -Destination $ReleasePath
Write-Host "Published $ReleasePath"
