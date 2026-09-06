"""Seal existing P9 parameters and outcome-blind source selection before replay."""
from pathlib import Path
import hashlib
import json
import shutil
from datetime import datetime, timezone
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'reports/p9/paired_residual/independent'

def main():
    seal = OUT / 'sealed'
    seal.mkdir(parents=True, exist_ok=True)
    assert not (seal / 'protocol.json').exists(), 'Do not overwrite an existing seal'
    dev = ROOT / 'reports/p9/paired_residual/corrected_results'
    calibration = json.loads((dev / 'calibration.json').read_text())
    primary = max(calibration, key=lambda c: c['threshold'])['held_out_source']
    selected = ROOT / 'reports/p9/paired_residual/proposed_independent_sources.csv'
    sources = pd.read_csv(selected)
    assert len(sources) == 3
    hashes = {}
    for row in sources.itertuples():
        path = ROOT / 'data/raw/uav_sead' / row.relative_path
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row.sha256
        assert row.log_key.replace('/', '__') not in [c['held_out_source'] for c in calibration]
    cfg = yaml.safe_load((ROOT / 'configs/p9_sitl_injection.yaml').read_text())['paths']
    files = [selected, dev / 'calibration.json', ROOT / 'configs/p9_paired_residual.yaml',
             ROOT / 'reports/p9/stage1_reassessment/native_replay/modules.json',
             ROOT / 'src/hs_aerots/paired_replay.py', ROOT / 'src/hs_aerots/replay_clock.py',
             ROOT / 'src/hs_aerots/replay_detection.py', ROOT / 'src/hs_aerots/baseline.py',
             ROOT / 'src/hs_aerots/sitl_injection.py', ROOT / 'scripts/p9/audit_stage1.py',
             ROOT / 'scripts/p9/run_independent.sh']
    files += [dev / f"noise_{c['held_out_source']}.npy" for c in calibration]
    files += [ROOT / cfg[k] for k in ('scaler_mean','scaler_std','feature_dictionary',
                                    'core_channels','topic_module_mapping','stage1_model','stage2_model')]
    files += list((ROOT / 'reports/p9/replay_scripts').glob('*'))
    for path in files:
        if not path.is_file(): continue
        rel = path.relative_to(ROOT).as_posix()
        hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
        if path.stat().st_size < 10_000_000:
            shutil.copy2(path, seal / path.name)
    (seal / 'sha256.json').write_text(json.dumps(hashes, indent=2))
    protocol = dict(sealed_at_utc=datetime.now(timezone.utc).isoformat(), primary_calibration=primary,
        primary_rule='Existing largest numerical threshold and its paired noise vector; chosen before replay; not a guarantee of conservative behavior across noise vectors',
        other_calibrations='Report all two as sensitivity; never select by test performance',
        fit_on_test=False, refit_on_development=False, onset_evaluation_only_s=30.,
        sources=sources.to_dict('records'), n_sources=3, faults=12, independent_normal_targets=12,
        matched_references=12, conditions_per_source_per_mutation=['baseline','fault','normal'],
        protocol='Existing generic replay, original binaries and schedules, EKF no -r; exact sensor clock; original features/scalers; 3-window global residual gate; 54 publisher-mapped candidates; worst ties',
        missing_or_incomplete='Keep all planned trials; report unavailable outputs and coverage, no replacements or tuning',
        effect_failures='Retain all 12 faults in primary denominator; report effect audit separately',
        latency='First post-onset causal gate minus 30 s; misses explicitly censored, aggregate delay conditional on detection; ranking uses all gated windows',
        independence='No P9 development source overlap. Normal metadata/field coverage inspected before seal. P2 historical scaler exposure is not excluded; no globally unseen-training claim.',
        previous_plan_superseded='User now requires freezing existing scalers/thresholds; no proposed P11 scaler refit',
        execution='Four parallel mutation workers; baseline/fault/normal serial within each, sources serial; timeout ceil(source duration)+20 s')
    (seal / 'protocol.json').write_text(json.dumps(protocol, indent=2))
    print(json.dumps(protocol, indent=2))

if __name__ == '__main__': main()
