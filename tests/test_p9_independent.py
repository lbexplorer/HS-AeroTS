"""Guard independent validation against fitting and label-dependent prediction."""
import ast
import importlib.util
from pathlib import Path
import numpy as np
import pytest

PATH=Path(__file__).resolve().parents[1]/'scripts/p9/evaluate_independent.py'
spec=importlib.util.spec_from_file_location('independent_eval',PATH)
evaluation=importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)

def test_independent_entrypoint_has_no_fit_or_truth_access_in_prediction():
    tree=ast.parse(PATH.read_text())
    assert not any(isinstance(n,ast.Name) and n.id.startswith('fit_') for n in ast.walk(tree))
    for node in tree.body:
        if isinstance(node,ast.FunctionDef) and node.name in ('infer_pair','inference'):
            strings=[n.value for n in ast.walk(node) if isinstance(n,ast.Constant) and isinstance(n.value,str)]
            assert not {'mutation_id','ground_truth_module','onset_evaluation_only_s'}.intersection(strings)

def test_prediction_ignores_metadata_and_preserves_causal_gate():
    target=dict(features=np.r_[np.zeros((4,2)),np.ones((6,2))*4],times=np.arange(10))
    ref=dict(features=np.zeros((10,2)),times=np.arange(10))
    args=(9,9,np.ones(2),np.arange(2),np.eye(2),3)
    first=evaluation.infer_pair(target,ref,*args)
    changed={**target,'ground_truth_module':'wrong','mutation_id':'wrong','onset':-100}
    second=evaluation.infer_pair(changed,ref,*args)
    np.testing.assert_array_equal(first['gate'],second['gate'])
    np.testing.assert_array_equal(first['ranks'],second['ranks'])
    assert np.flatnonzero(first['gate'])[0]==6
    # Equal publishers/identical evidence retain worst ranks, not a truth-selected tie.
    np.testing.assert_array_equal(first['ranks'],[2,2])

def test_empty_joint_support_is_not_a_healthy_prediction():
    x=dict(features=np.zeros((10,2)),times=np.arange(10))
    with pytest.raises(ValueError,match='Insufficient'):
        evaluation.infer_pair(x,x,1,1,np.ones(2),np.arange(2),np.eye(2),3)
