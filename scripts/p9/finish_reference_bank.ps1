$ErrorActionPreference = 'Stop'
Set-Location 'D:\UAV'
$p15Base = 'reports/p15_reference_bank'
$p15Pid = [int](Get-Content "$p15Base/runner.pid")
while (-not (Test-Path "$p15Base/healthy_repeats/input_sha256.txt")) {
    if (-not (Get-Process -Id $p15Pid -ErrorAction SilentlyContinue)) { throw 'Healthy replay stopped before completion' }
    Start-Sleep -Seconds 15
}
& .venv/Scripts/python.exe scripts/p9/prepare_reference_bank.py
if ($LASTEXITCODE -ne 0) { throw 'Bank cache failed' }
foreach ($p15Phase in @('freeze','predict','score')) {
    & .venv/Scripts/python.exe scripts/p9/run_reference_bank.py --phase $p15Phase
    if ($LASTEXITCODE -ne 0) { throw "Bank phase failed: $p15Phase" }
}
'Reference bank experiment completed'
