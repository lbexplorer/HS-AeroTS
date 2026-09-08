"""Generate revised paper tables/figures from frozen results, never refit models."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
PAPER=ROOT/'paper';GEN=PAPER/'generated';OUT=ROOT/'reports/paper_finalization_20260908'
SOURCES={}
def read(path):
    p=ROOT/path;SOURCES[path]=hashlib.sha256(p.read_bytes()).hexdigest();return pd.read_csv(p)
def esc(s):return str(s).replace('_',r'\_').replace('&',r'\&').replace('%',r'\%')
def count(x,n=12):return f'{round(float(x)*n)}/{n}'
def table(caption,label,headers,rows,widths=None,note=''):
    spec=widths or ('l'+'c'*(len(headers)-1))
    lines=[r'\begin{table}[htbp]',r'\centering\footnotesize',r'\caption{'+caption+'}',r'\label{'+label+'}',r'\renewcommand{\arraystretch}{1.15}',r'\setlength{\tabcolsep}{4pt}',r'\begin{tabular}{'+spec+'}',r'\toprule',' & '.join(headers)+r'\\',r'\midrule']
    lines+=[' & '.join(str(x) for x in row)+r'\\' for row in rows]
    lines += [r'\bottomrule',r'\end{tabular}']
    if note:lines +=[r'\par\smallskip\parbox{0.98\linewidth}{\scriptsize '+note+'}']
    return '\n'.join(lines+[r'\end{table}',''])
def write(name,text):(GEN/name).write_text(text,encoding='utf-8')

def main():
    GEN.mkdir(exist_ok=True)
    frozen=read('reports/p15_channel_gate/summary.csv').query("dataset=='transfer' and method=='original_primary'").iloc[0]
    joint=read('reports/p15_joint_support/summary.csv').query("dataset=='transfer' and method=='original_primary'").iloc[0]
    rows=[]
    for label,col,kind in [('Fault detections','detected','int'),('Normal runs with an alarm','normal_alarms','int'),('Fault runs with pre-onset alarms','pre_onset','int'),('Clean fault-specific detections','clean_fault_only','int'),('Top-1','top1','frac'),('Top-3','top3','frac'),('Top-5','top5','frac'),('MRR','mrr','float'),('Median detection delay (s)','delay_median_s','delay'),('Maximum detection delay (s)','delay_max_s','delay')]:
        vals=[]
        for r in [frozen,joint]:
            v=r[col];vals.append(f'{int(v)}/12' if kind=='int' else count(v) if kind=='frac' else f'{v:.4f}' if kind=='float' else f'{v:.3f}')
        rows.append([label,*vals])
    write('paired_transfer_table.tex',table('Paired residuals on the same transfer targets: frozen parameters and exploratory common-support processing.','tab:paired_transfer',['Measure',r'\shortstack{Frozen paired\\residual frontend}',r'\shortstack{Common-support\\frontend}'],rows,
        r'p{6.0cm}cc',r'The threshold, feature noise and publisher allocation are unchanged. Both columns use 12 fault and 12 normal targets from the same three sources; normal alarms cover the complete available run. Delays are conditional on detection (12 and 10 detections, respectively); misses are retained in ranking denominators. The right column was evaluated after transfer data exposure.'))
    dev=read('reports/p9/paired_residual/corrected_results/summary.csv').set_index('method')
    methods=['original_stage1_original_shap','residual_gate_original_shap','paired_residual']
    rows=[]
    for label,col,kind in [('Fault detections','detected_runs','int'),('Normal alarms','normal_false_alarm_runs','int'),('Top-1','top1','frac'),('Top-3','top3','frac'),('Top-5','top5','frac'),('MRR','mrr','float'),('Clean detections','clean_fault_only_detected_runs','int')]:
        vals=[dev.loc[m,col] for m in methods]
        rows.append([label,*[f'{int(v)}/12' if kind=='int' else count(v) if kind=='frac' else f'{v:.4f}' for v in vals]])
    write('development_comparison.tex',table('Corrected development comparison using the same targets and references.','tab:s_dev',['Measure',r'\shortstack{Original gate\\and SHAP}',r'\shortstack{Residual gate\\and SHAP}',r'\shortstack{Residual gate\\and evidence}'],rows,note='The original gate is the frozen learned Stage 1 detector. All columns retain 54 candidate modules, all 12 fault trials, and independent normal targets. These are development comparisons, not independent confirmation.'))
    consistency=read('reports/p12/semantic_mapping/consistency_summary.csv')
    rows=[]
    for r in consistency.itertuples():
        rows.append([esc(r.scope),r.k,f'{r.consistency_mean:.4f}',f'{r.random_consistency:.4f}',f'{r.hit_rate_mean:.4f}',f'{r.random_hit_rate:.4f}'])
    write('semantic_sensitivity.tex',table('Complete document-derived semantic agreement sensitivity (five-seed means).','tab:s_semantic',['Scope','$K$','Consistency','Random','Hit','Random Hit'],rows,note='Shared channels count as non-matches for specific domains. This is agreement with an author-defined reference, not independent physical ground truth. The original and document-derived maps differ on 11/87 channels.'))
    f=read('reports/p15_joint_support/results_by_run.csv').query("dataset=='transfer' and method=='original_primary'")
    labels={'commander_nav_state_override':'Commander','ekf2_innovation_bias':'EKF2','inav_local_z_freeze':'INAV','land_detector_state_inversion':'Land Detector'}
    rows=[]
    for mutation,d in f.groupby('mutation_id'):
        a=d[d.condition=='fault'];b=d[d.condition=='normal']
        rows.append([labels[mutation],f'{a.detected.sum()}/3',f'{b.any_alarm.sum()}/3',f'{a.pre_onset_alarm.sum()}/3',f'{a.top1.sum()}/3',f'{a.top3.sum()}/3',f'{a.top5.sum()}/3',f'{a.mrr.mean():.4f}',f'{a.delay_s.mean():.3f}'])
    write('mutation_comparison.tex',table('Common-support frontend with the frozen paired gate, by mutation.','tab:s_mutation',['Mutation','Detect','Normal','Pre','T1','T3','T5','MRR','Delay (s)'],rows,note='Normal denotes normal targets with any alarm; Pre denotes fault trials with a pre-onset alarm. Delay is the mean among detections only. EKF2 post-onset recall coexists with normal and pre-onset alarms.'))
    normals=f[f.condition=='normal'].set_index('run_id')
    rows=[]
    for r in f[f.condition=='fault'].itertuples():
        n=normals.loc[r.run_id.rsplit('__',1)[0]+'__baseline']
        date=r.source_log.split('__')[0]
        rows.append([labels[r.mutation_id],date,'Yes' if r.detected else 'No','Yes' if n.any_alarm else 'No','Yes' if r.pre_onset_alarm else 'No','--' if pd.isna(r.rank) else int(r.rank),'--' if pd.isna(r.delay_s) else f'{r.delay_s:.3f}'])
    write('per_run_common_support.tex',table('All transfer fault trials under common-support processing.','tab:s_runs',['Mutation','Source date','Detect','Normal','Pre','Rank','Delay (s)'],rows,note='The 2018-12-20 Commander effect-exclusivity check failed and the trial remains in the denominator. Rank 2 can include a tied publisher. Full source times are identified in Section S1.'))
    allframes=[]
    for exp,short in [('p15_channel_gate','Channel'),('p15_joint_support','Common'),('p15_reference_bank','Bank')]:
        d=read(f'reports/{exp}/summary.csv');d['experiment']=exp;allframes.append(d)
    allframe=pd.concat(allframes,ignore_index=True)
    names={'original_primary':'Frozen paired','channel_gate_fixed_rank':'New gate / fixed rank','channel_gate_new_rank':'New gate / new rank'}
    for dataset in ['development','transfer']:
        rows=[]
        for r in allframe[allframe.dataset==dataset].itertuples():
            label={'p15_channel_gate':'Channel','p15_joint_support':'Common','p15_reference_bank':'Bank'}[r.experiment]
            rows.append([label,names[r.method],int(r.detected),int(r.normal_alarms),int(r.pre_onset),int(r.clean_fault_only),f'{round(r.top1*12)}/{round(r.top3*12)}/{round(r.top5*12)}',f'{r.mrr:.4f}'])
        write(f'all_ablations_{dataset}.tex',table(f'All supplementary calibration comparisons: {dataset}.','tab:s_'+dataset,['Frontend','Gate / evidence','Detect','Normal','Pre','Clean','T1/T3/T5','MRR'],rows,note='All count denominators are 12; each Top-K count also has denominator 12. Bank uses new normal targets, while Channel and Common use the older targets. Fixed rank retains the frozen comparator\'s offline rank and is not a rank computed at the new alarm time. Development normal data participate in calibration; their rates are not independent validation.'))
    transfer=read('reports/p9/paired_residual/independent/summary.csv')
    write('frozen_fold_sensitivity.tex',table('All calibrations frozen before the first transfer replay.','tab:s_folds',['Excluded development date','Primary','Detect','Normal','Pre','T1/T3/T5','MRR'],[[r.calibration.split('__')[0],'Yes' if r.primary else 'No',int(r.detected_runs),int(r.normal_false_alarm_runs),int(r.fault_pre_onset_alarm_runs),f'{round(r.top1*12)}/{round(r.top3*12)}/{round(r.top5*12)}',f'{r.mrr:.4f}'] for r in transfer.itertuples()],note='All count denominators are 12. The primary calibration was selected before transfer using the largest numerical threshold and its associated noise vector, not transfer outcomes.'))
    for file,suffix in [('comparison_fixed_rank.csv','full'),('comparison_post30_common_exposure.csv','post30')]:
        d=read('reports/p14_within_flight_calibration/'+file)
        write('p14_'+suffix+'.tex',table('Within-flight calibration: '+('original exposure schedules' if suffix=='full' else 'common post-30-s alarm exposure')+'.','tab:s_p14_'+suffix,['Gate','Detect','Normal','Pre','Clean','T1/T3/T5','MRR'],[[{'frozen':'Frozen paired','optimized_q90_w15':'q90 + 15-s warm-up','within_flight':'Within-flight'}[r.gate],r.detected_runs,r.normal_false_alarms,r.pre_onset_alarms,r.clean_fault_only_detected,f'{r.top1}/{r.top3}/{r.top5}',f'{r.mrr:.4f}'] for r in d.itertuples()],note='All count denominators are 12. These gate comparisons hold the original offline module ranks fixed. Within-flight detection starts at 30 s, so its zero pre-onset count is imposed by the schedule. Post-30 exposure also excludes earlier comparator alarms; it is not evidence that they did not occur.'))
    # A main-text evidence figure without duplicating the full semantic tables.
    masking=read('reports/p4/masking_results.csv');modules=read('reports/p13/conservative_graph/module_rankings.csv')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'pdf.fonttype':42,'ps.fonttype':42})
    fig,axes=plt.subplots(1,2,figsize=(10.8,3.3),gridspec_kw={'width_ratios':[1,1.12]})
    for mask,label,color in [('validation_shap_top_k','SHAP-ranked','#226e9c'),('uniform_random_k','Random','#9b9b9b')]:
        q=masking[masking['mask']==mask].sort_values('k');axes[0].plot(q.k,q.macro_f1_drop_mean,'o-',label=label,color=color,lw=1.8)
    axes[0].set(xlabel='Number of masked features',ylabel='Macro-F1 decrease',title='(a) Prediction relevance under masking');axes[0].legend(frameon=False);axes[0].set_xticks([10,25,50,100]);axes[0].grid(axis='y',alpha=.2)
    q=modules[modules['mode']=='producer_only'].sort_values('rank').head(5).iloc[::-1]
    axes[1].barh(q.module.str.replace('src/modules/','',regex=False),q.shap_share,color='#378679')
    axes[1].set(xlabel='Normalized SHAP share',title='(b) Static source-tree candidates');axes[1].grid(axis='x',alpha=.2)
    for ax in axes:ax.spines[['top','right']].set_visible(False)
    fig.tight_layout(w_pad=2);fig.savefig(PAPER/'figures/figure_4_evidence_revision.pdf',bbox_inches='tight');plt.close(fig)
    # Numeric source ledger contains exact original rows, not manually rounded values.
    ledger={'sources_sha256':SOURCES,'main_transfer':pd.DataFrame([frozen,joint]).to_dict(orient='records'),'development':dev.reset_index().to_dict(orient='records'),'all_exploratory':allframe.to_dict(orient='records')}
    (OUT/'table_source_ledger.json').write_text(json.dumps(ledger,indent=2),encoding='utf-8')
    allframe.to_csv(OUT/'supplement_calibration_rows.csv',index=False)
    print(f'Generated {len(list(GEN.glob("*.tex")))} tables and main evidence figure from {len(SOURCES)} frozen sources')

if __name__=='__main__':main()
