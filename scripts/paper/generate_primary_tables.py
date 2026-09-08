"""Generate existing real-flight table bodies from their frozen summaries."""
from pathlib import Path
import hashlib,json
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];GEN=ROOT/'paper/generated'
SOURCES={};ROWS={}
def read(name):
    p=ROOT/name;SOURCES[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    data=json.loads(p.read_text(encoding='utf-8')) if p.suffix=='.json' else pd.read_csv(p)
    ROWS[name]=data if isinstance(data,dict) else data.to_dict('records')
    return data
def pm(mean,sd):return f'${mean:.4f}\\pm{sd:.4f}$'
def main():
    GEN.mkdir(exist_ok=True)
    stage1=read('reports/p2/baseline_summary.json')['metrics']
    primary=read('reports/p3/method_summary.csv').set_index('method')
    direct=read('reports/p10/direct_five_seeds/method_summary.csv').set_index('method')
    lines=[]
    def append(fields):lines.append(' & '.join(fields)+r'\\')
    append(['Binary detection',r'\textbf{HS-AeroTS Stage 1}',*[pm(stage1['test_'+m]['mean'],stage1['test_'+m]['std']) for m in ('auprc','auroc')],'--','--'])
    lines.append(r'\addlinespace[2pt]')
    for task,label,name in [('Conditional four-domain diagnosis',r'\textbf{HS-AeroTS Stage 2}','stage2_lightgbm'),('','Random Forest','stage2_random_forest'),('','Majority','majority'),('','Stratified random','stratified_random'),('Complete five-class prediction',r'\textbf{HS-AeroTS Cascade}','hs_aerots_cascade'),('','Direct Five-Class','direct_five_class_lightgbm')]:
        row=(direct if name=='direct_five_class_lightgbm' else primary).loc[name]
        assert int(row.runs)==5
        if name=='hs_aerots_cascade':lines.append(r'\addlinespace[2pt]')
        f1=f'{row.macro_f1_mean:.4f}' if name=='majority' else pm(row.macro_f1_mean,row.macro_f1_std)
        ba='--' if name in ('majority','stratified_random') else pm(row.balanced_accuracy_mean,row.balanced_accuracy_std)
        append([task,label,'--','--',f1,ba])
    (GEN/'primary_results_rows.tex').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    uncertainty=read('reports/p13/absolute_uncertainty/absolute_metric_cluster_ci.csv')
    protocols={'fixed_chronological':'Fixed','purged_14_windows':'Purged','leave_log_out':'Leave-log-out','alfa_zero_shot':'ALFA zero-shot','uncategorized_screening':'Uncategorized'}
    tasks={'stage1':'Stage 1 AUPRC','stage2_anomaly_only':'Stage 2 Macro-F1','cascade_five_class':'Cascade Macro-F1','direct_five_class':'Direct Five-Class Macro-F1','flight_level':'Flight-level AUPRC'}
    lines=[]
    for r in uncertainty.itertuples():
        # Task names are validated, not silently substituted.
        append([protocols[r.protocol],tasks[r.task],f'{r.point_mean:.4f}',f'{r.seed_sd:.4f}',f'[{r.ci_low:.4f}, {r.ci_high:.4f}]'])
    (GEN/'absolute_uncertainty_rows.tex').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    for name in ('primary_results','absolute_uncertainty'):
        template=(ROOT/'paper/templates'/f'{name}_table.tex').read_text(encoding='utf-8')
        rows=(GEN/f'{name}_rows.tex').read_text(encoding='utf-8')
        (GEN/f'{name}_table.tex').write_text(template.replace('% GENERATED_ROWS',rows),encoding='utf-8')
    (ROOT/'reports/paper_finalization_20260908/primary_table_source_ledger.json').write_text(json.dumps({'sources_sha256':SOURCES,'source_rows':ROWS},indent=2),encoding='utf-8')
    print('Generated primary result and uncertainty table rows from frozen summaries.')
if __name__=='__main__':main()
