#%%

import numpy as np
import os
from pathlib import Path
from numba import guvectorize, float64, int32, njit

datasets = [
    ['biwi_eth.txt'], 
    ['biwi_hotel.txt'], 
    # ['students001.txt', 'students003.txt'],
    # ['crowds_zara01.txt'], 
    # ['crowds_zara02.txt'],
]

#%%

def calculate_displacement_error(y, y_hat):
    # y_hat dim: (num_samples x num_scenarios x num_leadtime x 2)
    return np.sqrt(np.sum((y-y_hat)**2, axis=-1)) 

def fde_ml(y, y_hat):
    """ 
        average final displacement error of the most likely trajectory (indexed 0) 
        across all samples in the dataset 
    """
    return calculate_displacement_error(y[:,0,-1], y_hat[:,0,-1]).mean()

def ade_ml(y, y_hat):
    """ 
        average displacement error of the most likely trajectory (indexed 0) 
        across all samples in the dataset 
    """
    return calculate_displacement_error(y[:,0], y_hat[:,0]).mean()

def fde_best20(y, y_hat):
    """
        final displace error of the best trajectory (trajectory with 
        lowest errors) across all samples in the dataset 
    """
    errors = calculate_displacement_error(y[:,:,-1], y_hat[:,:,-1])
    best_idx = np.argmin(errors, axis=1)
    avg_error = 0
    for sample_idx, traj_idx in enumerate(best_idx):
        avg_error += errors[sample_idx, traj_idx] 
    avg_error /= len(best_idx)
    return avg_error

def ade_best20(y, y_hat):
    """
        average displacement error of the best trajectory (trajectory with
        lowest error) averaged across all samples in the dataset
    """
    errors = calculate_displacement_error(y[:,:,:], y_hat[:,:,:]).mean(axis=2)
    best_idx = np.argmin(errors, axis=1)
    avg_error = 0
    for sample_idx, traj_idx in enumerate(best_idx):
        avg_error += errors[sample_idx, traj_idx] 
    avg_error /= len(best_idx)
    return avg_error


#%%
def fde_topN(y, y_hat, N=1, axis=(0,1)):
    """
        average displacement error of the best trajectory (trajectory with
        lowest error) averaged across all samples in the dataset
    """
    errors = calculate_displacement_error(y[:,:,-1], y_hat[:,:,-1])
    best_idxs = np.argsort(errors, axis=1)[:,:N]
    avg_error = np.zeros((len(errors), N))
    for sample_idx, traj_idx in enumerate(best_idxs):
        avg_error[sample_idx, :] = errors[sample_idx, traj_idx] 
    return avg_error.mean(axis=axis)

# print(fde_topN(pred_gts, pred_ours, N=1, axis=0).round(2))
# print(fde_best20(pred_gts, pred_ours).round(2))

def ade_topN(y, y_hat, N=1, axis=(0,1)):
    """
        average displacement error of the best trajectory (trajectory with
        lowest error) averaged across all samples in the dataset
    """
    errors = calculate_displacement_error(y[:,:,:], y_hat[:,:,:]).mean(axis=2)
    best_idxs = np.argsort(errors, axis=1)[:,:N]
    avg_error = np.zeros((len(errors), N))
    for sample_idx, traj_idx in enumerate(best_idxs):
        avg_error[sample_idx, :] = errors[sample_idx, traj_idx] 
    return avg_error.mean(axis=axis)

# print(ade_topN(pred_gts, pred_ours, N=2, axis=0).round(2))
# print(ade_best20(pred_gts, pred_ours).round(2))
#%%

def fde_topNPercent(y, y_hat, percentage=0.1, axis=(0,1)):
    """
        average displacement error of the best trajectory (trajectory with
        lowest error) averaged across all samples in the dataset
    """
    errors = calculate_displacement_error(y[:,:,-1], y_hat[:,:,-1])
    n_trajectories = y_hat.shape[1]
    N = int(n_trajectories * percentage)
    # print(N)
    return fde_topN(y, y_hat, N=N, axis=axis)

# print(fde_topN(pred_gts, pred_ours, N=2, axis=0).round(2))
# print(fde_topNPercent(pred_gts, pred_ours, percentage=0.2, axis=0).round(2))

def ade_topNPercent(y, y_hat, percentage=0.1, axis=(0,1)):
    """
        average displacement error of the best trajectory (trajectory with
        lowest error) averaged across all samples in the dataset
    """
    errors = calculate_displacement_error(y[:,:,:], y_hat[:,:,:]).mean(axis=2)
    n_trajectories = y_hat.shape[1]
    N = int(n_trajectories * percentage)
    # print(N)
    return ade_topN(y, y_hat, N=N, axis=axis)

# print(ade_topN(pred_gts, pred_ours, N=2, axis=0).round(2))
# print(ade_topNPercent(pred_gts, pred_ours, percentage=0.2, axis=0).round(2))
#%%


@njit('f8[:](f8[:,:,:,:], f8[:,:,:,:], f8)', cache = False, )
def energy_score(y, x, K=1):
    """ This implementation only takes the temporal aspects into account but also
        does not separate the spatial dimensions (flatten out together).
    """
    # K=1
    K=int(K)
    d=2.0
    b=1.0
    n_samples = x.shape[0]
    n_scenarios = x.shape[1]
    n_horizon = x.shape[2]
    n_dims = x.shape[3]
    M = n_scenarios
    # K = np.abs(K)
    # K = M if K >= M else K
    K = M
    es = np.empty((n_samples,))
    for s in range(n_samples):
        #
        ed = 0
        for j in range(M):
            # print(y[s,0].shape)
            # print((x[s,j]-y[s,0]).shape)
            # Equivalent to the Frobenius distance
            ed += (np.sum(np.abs(x[s,j]-y[s,0])**d)**(1/d))**b
        ed/=(M*n_dims)
        #
        ei=0
        c = 0
        for j in range(M):
            for k in range(K):
                ei += (np.sum(np.abs((x[s,j]-x[s,(j+k+1)%M]))**d)**(1/d))**b
                c += 1
        ei /= (c*n_dims)
        es[s] = ed - 0.5 * ei
    return es

# print(energy_score(pred_gts, pred_ours, K=pred_ours.shape[1]).mean().round(3))
#%%

@njit('f8[:,:](f8[:,:,:,:], f8[:,:,:,:], f8)', cache = False, )
def energy_score_temporal(y, x, K=1):
    """ This implementation only takes the temporal aspects into account """
    # K=1
    K=int(K)
    d=2.0
    b=1.0
    n_samples = x.shape[0]
    n_scenarios = x.shape[1]
    n_horizon = x.shape[2]
    n_dims = x.shape[3]
    M = n_scenarios
    # K = np.abs(K)
    # K = M if K >= M else K
    K = M
    d = n_horizon
    es = np.zeros((n_samples,n_dims))
    for s in range(n_samples):
        #
        ed = np.zeros((n_dims))
        for j in range(M):
            # print(y[s,0].shape)
            # print((x[s,j]-y[s,0]).shape)
            # print(np.sum(np.abs(x[s,j]-y[s,0])**d, axis=0).shape)
            # equivalent to the Minkowsky column distance    
            ed += (np.sum(np.abs(x[s,j]-y[s,0])**d, axis=0)**(1/d))**b
        ed/=M
        #
        ei=np.zeros((n_dims))
        c = 0
        for j in range(M):
            for k in range(K):
                ei += (np.sum(np.abs((x[s,j]-x[s,(j+k+1)%M]))**d, axis=0)**(1/d))**b
                c += 1
        ei /= c
        es[s] = ed - 0.5 * ei
    return es

# print(energy_score_temporal(pred_gts, pred_ours, K=pred_ours.shape[1]).shape)
# print(energy_score_temporal(pred_gts, pred_ours, K=pred_ours.shape[1]).mean().round(3))
#%%

@njit('f8[:,:](f8[:,:,:,:], f8[:,:,:,:], f8)', cache = False, )
def energy_score_spatial(y, x, K=1):
    """ This implementation only takes the spatial aspects into account """
    # K=1
    K=int(K)
    d=2.0
    b=1.0
    n_samples = x.shape[0]
    n_scenarios = x.shape[1]
    n_horizon = x.shape[2]
    n_dims = x.shape[3]
    M = n_scenarios
    # K = np.abs(K)
    # K = M if K >= M else K
    K = M
    d = n_dims
    es = np.zeros((n_samples,n_horizon))
    for s in range(n_samples):
        #
        ed = np.zeros((n_horizon))
        for j in range(M):
            # print(y[s,0].shape)
            # print((x[s,j]-y[s,0]).shape)
            # equivalent to the Minkowsky row distance    
            ed += (np.sum(np.abs(x[s,j]-y[s,0])**d, axis=1)**(1/d))**b
        ed/=M
        #
        ei=np.zeros((n_horizon))
        c = 0
        for j in range(M):
            for k in range(K):
                ei += (np.sum(np.abs((x[s,j]-x[s,(j+k+1)%M]))**d, axis=1)**(1/d))**b
                c += 1
        ei /= c
        es[s] = ed - 0.5 * ei
    return es

# print(energy_score_spatial(pred_gts, pred_ours, K=pred_ours.shape[1]).shape)
# print(energy_score_spatial(pred_gts, pred_ours, K=pred_ours.shape[1]).mean().round(3))
#%%

@njit('f8[:](f8[:,:,:,:], f8[:,:,:,:], f8)', cache = False, )
def energy_score_spatiotemporal(y, x, K=1):
    """ This implementation respects both spatial and temporal aspects"""
    # K=1
    K=int(K)
    d=2.0
    b=1.0
    n_samples = x.shape[0]
    n_scenarios = x.shape[1]
    n_horizon = x.shape[2]
    n_dims = x.shape[3]
    M = n_scenarios
    # K = np.abs(K)
    # K = M if K >= M else K
    K=M
    es = np.zeros((n_samples,))
    for s in range(n_samples):
        #
        ed = 0
        for j in range(M):
            # print(y[s,0].shape)
            # print((x[s,j]-y[s,0]).shape)
            d = n_horizon
            ed_temporal = (np.sum(np.abs(x[s,j]-y[s,0])**d, axis=0)**(1/d))**b
            d = n_dims
            ed_spatial = (np.sum(np.abs(x[s,j]-y[s,0])**d, axis=1)**(1/d))**b
            # print(ed_temporal.shape)
            # print(ed_spatial.shape)
            # ed += (ed_temporal.mean() + ed_spatial.mean())
            ed += np.append(ed_temporal, ed_spatial).mean()
        ed/=M
        #
        ei=0
        c = 0
        for j in range(M):
            for k in range(K):
                d = n_horizon
                ei_temporal = (np.sum(np.abs((x[s,j]-x[s,(j+k+1)%M]))**d, axis=0)**(1/d))**b
                d = n_dims
                ei_spatial = (np.sum(np.abs((x[s,j]-x[s,(j+k+1)%M]))**d, axis=1)**(1/d))**b
                # ei += (ei_temporal.mean() + ei_spatial.mean())
                ei += np.append(ei_temporal, ei_spatial).mean()
                c += 1
        ei /= c
        es[s] = ed - 0.5 * ei
    return es

# print(energy_score_spatiotemporal(pred_gts, pred_ours, K=pred_ours.shape[1]).shape)
# print(energy_score_spatiotemporal(pred_gts, pred_ours, K=pred_ours.shape[1]).mean().round(3))
#%%
if __name__ == "__main__":
#%%
    results_path = 'results/'
    for dataset in datasets:
        for scene in dataset:
            path_ours = os.path.join(results_path, scene.split(".")[0], "ours.npy")
            path_gts = os.path.join(results_path, scene.split(".")[0], "groundtruths.npy")
            pred_ours = np.load(path_ours)
            pred_gts = np.load(path_gts)[:,np.newaxis,:,:]
            print(scene)
            print(fde_ml(pred_gts, pred_ours).round(2))
            print(ade_ml(pred_gts, pred_ours).round(2))
            print(fde_best20(pred_gts, pred_ours).round(2))
            print(ade_best20(pred_gts, pred_ours).round(2))
            print(energy_score(pred_gts, pred_ours, K=pred_ours.shape[1]).mean().round(2))
            print("#"*20)
# %%
