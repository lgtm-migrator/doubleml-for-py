import numpy as np
import pytest
import math
import scipy

from sklearn.model_selection import KFold
from sklearn.base import clone

from sklearn.linear_model import LinearRegression, Lasso
from sklearn.ensemble import RandomForestRegressor

from dml.double_ml_plr import DoubleMLPLR

from dml.tests.helper_general import get_n_datasets
from dml.tests.helper_plr_manual import plr_dml1, plr_dml2, fit_nuisance_plr


# number of datasets per dgp
n_datasets = get_n_datasets()


@pytest.mark.parametrize('idx', range(n_datasets))
@pytest.mark.parametrize('learner', [RandomForestRegressor(max_depth=2, n_estimators=10),
                                     LinearRegression(),
                                     Lasso(alpha=0.1)])
@pytest.mark.parametrize('inf_model', ['IV-type', 'DML2018'])
@pytest.mark.parametrize('dml_procedure', ['dml1', 'dml2'])
def test_dml_plr(generate_data1, idx, learner, inf_model, dml_procedure):
    resampling = KFold(n_splits=2, shuffle=True)
    
    # Set machine learning methods for m & g
    ml_learners = {'ml_m': clone(clone(learner)),
                   'ml_g': clone(clone(learner))}
    
    dml_plr_obj = DoubleMLPLR(resampling,
                              ml_learners,
                              dml_procedure,
                              inf_model,
                              boot = None)
    data = generate_data1[idx]
    np.random.seed(3141)
    res = dml_plr_obj.fit(data['X'], data['y'], data['d'])
    
    np.random.seed(3141)
    smpls = [(train, test) for train, test in resampling.split(data['X'])]
    
    g_hat, m_hat = fit_nuisance_plr(data['y'], data['X'], data['d'],
                                    clone(learner), clone(learner), smpls)
    
    if dml_procedure == 'dml1':
        res_manual, se_manual = plr_dml1(data['y'], data['X'], data['d'],
                                         g_hat, m_hat,
                                         smpls, inf_model)
    elif dml_procedure == 'dml2':
        res_manual, se_manual = plr_dml2(data['y'], data['X'], data['d'],
                                         g_hat, m_hat,
                                         smpls, inf_model)
    
    assert math.isclose(res.coef_, res_manual, rel_tol=1e-9, abs_tol=1e-4)
    assert math.isclose(res.se_, se_manual, rel_tol=1e-9, abs_tol=1e-4)
    
    return

@pytest.mark.parametrize('idx', range(n_datasets))
@pytest.mark.parametrize('inf_model', ['IV-type', 'DML2018'])
@pytest.mark.parametrize('dml_procedure', ['dml1', 'dml2'])
def test_dml_plr_ols_manual(generate_data1, idx, inf_model, dml_procedure):
    learner = LinearRegression()
    resampling = KFold(n_splits=2, shuffle=False)
    
    # Set machine learning methods for m & g
    ml_learners = {'ml_m': clone(clone(learner)),
                   'ml_g': clone(clone(learner))}
    
    dml_plr_obj = DoubleMLPLR(resampling,
                              ml_learners,
                              dml_procedure,
                              inf_model,
                              boot = None)
    data = generate_data1[idx]
    res = dml_plr_obj.fit(data['X'], data['y'], data['d'])
    
    N = len(data['y'])
    smpls = []
    xx = int(N/2)
    smpls.append((np.arange(0, xx), np.arange(xx, N)))
    smpls.append((np.arange(xx, N), np.arange(0, xx)))
    
    # add column of ones for intercept
    o = np.ones((N,1))
    X = np.append(data['X'], o, axis=1)
    
    g_hat = []
    for idx, (train_index, test_index) in enumerate(smpls):
        ols_est = scipy.linalg.lstsq(X[train_index], data['y'][train_index])[0]
        g_hat.append(np.dot(X[test_index], ols_est))
    
    m_hat = []
    for idx, (train_index, test_index) in enumerate(smpls):
        ols_est = scipy.linalg.lstsq(X[train_index], data['d'][train_index])[0]
        m_hat.append(np.dot(X[test_index], ols_est))
    
    if dml_procedure == 'dml1':
        res_manual, se_manual = plr_dml1(data['y'], data['X'], data['d'],
                                         g_hat, m_hat,
                                         smpls, inf_model)
    elif dml_procedure == 'dml2':
        res_manual, se_manual = plr_dml2(data['y'], data['X'], data['d'],
                                         g_hat, m_hat,
                                         smpls, inf_model)
    
    assert math.isclose(res.coef_, res_manual, rel_tol=1e-9, abs_tol=1e-4)
    assert math.isclose(res.se_, se_manual, rel_tol=1e-9, abs_tol=1e-4)
    
    return



    
