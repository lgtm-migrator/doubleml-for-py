import numpy as np
from sklearn.model_selection import KFold, GridSearchCV
from sklearn.base import clone


def fit_nuisance_irm(Y, X, D, learner_m, learner_g, smpls, score, g0_params=None, g1_params=None, m_params=None):
    ml_g0 = clone(learner_g)
    ml_g1 = clone(learner_g)
    g_hat0 = []
    g_hat1 = []
    for idx, (train_index, test_index) in enumerate(smpls):
        if g0_params is not None:
            ml_g0.set_params(**g0_params[idx])
        train_index0 = np.intersect1d(np.where(D == 0)[0], train_index)
        g_hat0.append(ml_g0.fit(X[train_index0], Y[train_index0]).predict(X[test_index]))
    
    if score == 'ATE':
        for idx, (train_index, test_index) in enumerate(smpls):
            if g1_params is not None:
                ml_g1.set_params(**g1_params[idx])
            train_index1 = np.intersect1d(np.where(D == 1)[0], train_index)
            g_hat1.append(ml_g1.fit(X[train_index1], Y[train_index1]).predict(X[test_index]))
    else:
        for idx, (train_index, test_index) in enumerate(smpls):
            # fill it up, but its not further used
            g_hat1.append(np.zeros_like(g_hat0[idx]))

    ml_m = clone(learner_m)
    m_hat = []
    p_hat = []
    for idx, (train_index, test_index) in enumerate(smpls):
        if m_params is not None:
            ml_m.set_params(**m_params[idx])
        m_hat.append(ml_m.fit(X[train_index], D[train_index]).predict_proba(X[test_index])[:, 1])
        p_hat.append(np.mean(D[test_index]))
    
    return g_hat0, g_hat1, m_hat, p_hat


def tune_nuisance_irm(Y, X, D, ml_m, ml_g, smpls, score, n_folds_tune, param_grid_g, param_grid_m):
    g0_tune_res = [None] * len(smpls)
    g1_tune_res = [None] * len(smpls)
    m_tune_res = [None] * len(smpls)

    for idx, (train_index, test_index) in enumerate(smpls):
        # cv for ml_g0
        g0_tune_resampling = KFold(n_splits=n_folds_tune)
        g0_grid_search = GridSearchCV(ml_g, param_grid_g,
                                      cv=g0_tune_resampling)
        train_index0 = np.intersect1d(np.where(D == 0)[0], train_index)
        g0_tune_res[idx] = g0_grid_search.fit(X[train_index0, :], Y[train_index0])

        if score == 'ATE':
            # cv for ml_g1
            g1_tune_resampling = KFold(n_splits=n_folds_tune)
            g1_grid_search = GridSearchCV(ml_g, param_grid_g,
                                          cv=g1_tune_resampling)
            train_index1 = np.intersect1d(np.where(D == 1)[0], train_index)
            g1_tune_res[idx] = g1_grid_search.fit(X[train_index1, :], Y[train_index1])

        # cv for ml_m
        m_tune_resampling = KFold(n_splits=n_folds_tune)
        m_grid_search = GridSearchCV(ml_m, param_grid_m,
                                     cv=m_tune_resampling)
        m_tune_res[idx] = m_grid_search.fit(X[train_index, :], D[train_index])

    g0_best_params = [xx.best_params_ for xx in g0_tune_res]
    if score == 'ATTE':
        g1_best_params = None
    else:
        g1_best_params = [xx.best_params_ for xx in g1_tune_res]
    m_best_params = [xx.best_params_ for xx in m_tune_res]

    return g0_best_params, g1_best_params, m_best_params


def irm_dml1(Y, X, D, g_hat0, g_hat1, m_hat, p_hat, smpls, score):
    thetas = np.zeros(len(smpls))
    n_obs = len(Y)
    
    for idx, (train_index, test_index) in enumerate(smpls):
        u_hat0 = Y[test_index] - g_hat0[idx]
        u_hat1 = Y[test_index] - g_hat1[idx]
        thetas[idx] = irm_orth(g_hat0[idx], g_hat1[idx],
                               m_hat[idx], p_hat[idx],
                               u_hat0, u_hat1,
                               D[test_index], score)
    theta_hat = np.mean(thetas)
    
    ses = np.zeros(len(smpls))
    for idx, (train_index, test_index) in enumerate(smpls):
        u_hat0 = Y[test_index] - g_hat0[idx]
        u_hat1 = Y[test_index] - g_hat1[idx]
        ses[idx] = var_irm(theta_hat, g_hat0[idx], g_hat1[idx],
                           m_hat[idx], p_hat[idx],
                           u_hat0, u_hat1,
                           D[test_index], score, n_obs)
    se = np.sqrt(np.mean(ses))
    
    return theta_hat, se


def irm_dml2(Y, X, D, g_hat0, g_hat1, m_hat, p_hat, smpls, score):
    n_obs = len(Y)
    u_hat0 = np.zeros_like(Y)
    u_hat1 = np.zeros_like(Y)
    g_hat0_all = np.zeros_like(Y)
    g_hat1_all = np.zeros_like(Y)
    m_hat_all = np.zeros_like(Y)
    p_hat_all = np.zeros_like(Y)
    for idx, (train_index, test_index) in enumerate(smpls):
        u_hat0[test_index] = Y[test_index] - g_hat0[idx]
        u_hat1[test_index] = Y[test_index] - g_hat1[idx]
        g_hat0_all[test_index] = g_hat0[idx]
        g_hat1_all[test_index] = g_hat1[idx]
        m_hat_all[test_index] = m_hat[idx]
        p_hat_all[test_index] = p_hat[idx]
    theta_hat = irm_orth(g_hat0_all, g_hat1_all, m_hat_all, p_hat_all,
                         u_hat0, u_hat1, D, score)
    se = np.sqrt(var_irm(theta_hat, g_hat0_all, g_hat1_all,
                         m_hat_all, p_hat_all,
                         u_hat0, u_hat1,
                         D, score, n_obs))
    
    return theta_hat, se
    
def var_irm(theta, g_hat0, g_hat1, m_hat, p_hat, u_hat0, u_hat1, D, score, n_obs):
    if score == 'ATE':
        var = 1/n_obs * np.mean(np.power(g_hat1 - g_hat0 \
                      + np.divide(np.multiply(D, u_hat1), m_hat) \
                      - np.divide(np.multiply(1.-D, u_hat0), 1.-m_hat) - theta, 2))
    elif score == 'ATTE':
        var = 1/n_obs * np.mean(np.power(np.divide(np.multiply(D, u_hat0), p_hat) \
                      - np.divide(np.multiply(m_hat, np.multiply(1.-D, u_hat0)),
                                  np.multiply(p_hat, (1.-m_hat))) \
                      - theta * np.divide(D, p_hat), 2)) \
              / np.power(np.mean(np.divide(D, p_hat)), 2)
    else:
        raise ValueError('invalid score')
    
    return var

def irm_orth(g_hat0, g_hat1, m_hat, p_hat, u_hat0, u_hat1, D, score):
    if score == 'ATE':
        res = np.mean(g_hat1 - g_hat0 \
                      + np.divide(np.multiply(D, u_hat1), m_hat) \
                      - np.divide(np.multiply(1.-D, u_hat0), 1.-m_hat))
    elif score == 'ATTE':
        res = np.mean(np.divide(np.multiply(D, u_hat0), p_hat) \
                      - np.divide(np.multiply(m_hat, np.multiply(1.-D, u_hat0)),
                                  np.multiply(p_hat, (1.-m_hat)))) \
              / np.mean(np.divide(D, p_hat))
    
    return res

def boot_irm(theta, Y, D, g_hat0, g_hat1, m_hat, p_hat, smpls, score, se, bootstrap, n_rep, dml_procedure):
    u_hat0 = np.zeros_like(Y)
    u_hat1 = np.zeros_like(Y)
    g_hat0_all = np.zeros_like(Y)
    g_hat1_all = np.zeros_like(Y)
    m_hat_all = np.zeros_like(Y)
    p_hat_all = np.zeros_like(Y)
    n_folds = len(smpls)
    J = np.zeros(n_folds)
    for idx, (train_index, test_index) in enumerate(smpls):
        u_hat0[test_index] = Y[test_index] - g_hat0[idx]
        u_hat1[test_index] = Y[test_index] - g_hat1[idx]
        g_hat0_all[test_index] = g_hat0[idx]
        g_hat1_all[test_index] = g_hat1[idx]
        m_hat_all[test_index] = m_hat[idx]
        p_hat_all[test_index] = p_hat[idx]
        if dml_procedure == 'dml1':
            if score == 'ATE':
                J[idx] = -1.0
            elif score == 'ATTE':
                J[idx] = np.mean(-np.divide(D[test_index], p_hat_all[test_index]))

    if dml_procedure == 'dml2':
        if score == 'ATE':
            J = -1.0
        elif score == 'ATTE':
            J = np.mean(-np.divide(D, p_hat_all))
    
    if score == 'ATE':
        score = g_hat1_all - g_hat0_all \
                + np.divide(np.multiply(D, u_hat1), m_hat_all) \
                - np.divide(np.multiply(1.-D, u_hat0), 1.-m_hat_all) - theta
    elif score == 'ATTE':
        score = np.divide(np.multiply(D, u_hat0), p_hat_all) \
                - np.divide(np.multiply(m_hat_all, np.multiply(1.-D, u_hat0)),
                            np.multiply(p_hat_all, (1.-m_hat_all))) \
                - theta * np.divide(D, p_hat_all)
    else:
        raise ValueError('invalid score')
    
    n_obs = len(score)
    boot_theta = np.zeros(n_rep)
    if bootstrap == 'wild':
        # if method wild for unit test comparability draw all rv at one step
        xx_sample = np.random.normal(loc=0.0, scale=1.0, size=(n_rep, n_obs))
        yy_sample = np.random.normal(loc=0.0, scale=1.0, size=(n_rep, n_obs))
    
    for i_rep in range(n_rep):
        if bootstrap == 'Bayes':
            weights = np.random.exponential(scale=1.0, size=n_obs) - 1.
        elif bootstrap == 'normal':
            weights = np.random.normal(loc=0.0, scale=1.0, size=n_obs)
        elif bootstrap == 'wild':
            xx = xx_sample[i_rep,:]
            yy = yy_sample[i_rep,:]
            weights = xx / np.sqrt(2) + (np.power(yy,2) - 1)/2
        else:
            raise ValueError('invalid bootstrap method')

        if dml_procedure == 'dml1':
            this_boot_theta = np.zeros(n_folds)
            for idx, (train_index, test_index) in enumerate(smpls):
                this_boot_theta[idx] = np.mean(np.multiply(np.divide(weights[test_index], se),
                                                           score[test_index] / J[idx]))
            boot_theta[i_rep] = np.mean(this_boot_theta)
        elif dml_procedure == 'dml2':
            boot_theta[i_rep] = np.mean(np.multiply(np.divide(weights, se),
                                                    score / J))
    
    return boot_theta
