$ErrorActionPreference = 'Stop'
Set-Location 'D:\UAV'
$p9Base = 'reports/p9/paired_residual/independent'
$p9Pid = [int](Get-Content "$p9Base/recovery.pid")
while (-not (Test-Path "$p9Base/binary_sha256_after.txt")) {
    if (-not (Get-Process -Id $p9Pid -ErrorAction SilentlyContinue)) { throw 'Replay stopped before all outputs completed; inspect recovery.stderr.log' }
    Start-Sleep -Seconds 15
}
foreach ($p9Group in @('reference', 'normal')) {
    & .venv/Scripts/python.exe scripts/p9/audit_stage1.py --manifest "$p9Base/$p9Group/run_manifest.tsv" --output "$p9Base/${p9Group}_cache" --preserve-header-start --source-clock
    if ($LASTEXITCODE -ne 0) { throw "Feature audit failed: $p9Group" }
}
& .venv/Scripts/python.exe scripts/p9/evaluate_independent.py --phase predict
if ($LASTEXITCODE -ne 0) { throw 'Frozen inference failed' }
& .venv/Scripts/python.exe scripts/p9/evaluate_independent.py --phase score
if ($LASTEXITCODE -ne 0) { throw 'Scoring failed' }
& .venv/Scripts/python.exe scripts/p9/audit_independent.py
if ($LASTEXITCODE -ne 0) { throw 'Validity audit failed' }
'Independent evaluation completed'
