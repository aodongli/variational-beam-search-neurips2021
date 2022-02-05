import os
import sys
from datetime import datetime
import pickle
import multiprocessing
from multiprocessing import Pool
import numpy as np
import tensorflow as tf
import tensorflow_probability as tfp
tfd = tfp.distributions

sys.path.extend(['libs/'])
# general
from util import print_log, save_weights, load_weights
# data generator
from distribution_shift_generator import LongTransformedCifar10Generator
from distribution_shift_generator import LongTransformedSvhnGenerator
# Bayesian model
from model import vcl, bf
from model import BayesianCNN, get_bayesian_neural_net_with_prior
# hyperparameter search
from hyperparam_search import HyperparameterSearch

tf.logging.set_verbosity(tf.logging.ERROR)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

SVHN_SURROGATE_INITIAL_PRIOR_PATH_TEMPLATE = (
    "./meta_prior/svhn_prior_vcl.pkl%s")

CIFAR10_SURROGATE_INITIAL_PRIOR_PATH_TEMPLATE = (
    "./meta_prior/cifar_prior_vcl.pkl%s")


# parameters for SVHN
svhn_params = {
    "dataset_id": [1],
    "max_iter": [100], 
    "changerate": [3], 
    "task_size": [20000], 
    "lr": [0.00025], 
    "initial_prior_var": [1.], 
    "beta": [1.], # kl weight
    "diffusion": [0.9], # diffusion
    "independent": [False],
    "surrogate_initial_prior_path": [''],
    "validation": [False] 
}

# parameters for CIFAR10
cifar10_params = {
    "dataset_id": [0],
    "max_iter": [100], 
    "changerate": [3], 
    "task_size": [20000], 
    "lr": [0.0005], 
    "initial_prior_var": [1.], 
    "beta": [1.], # kl weight
    "diffusion": [0.9], # diffusion
    "independent": [False],
    "surrogate_initial_prior_path": [''],
    "validation": [False] 
}


# define train_and_eval() for vbs of CIFAR10
def train_and_eval(param, save_path):
    tf.reset_default_graph()
    random_seed = 1
    rng = np.random.RandomState(seed=random_seed)
    tf.compat.v1.set_random_seed(rng.randint(2**31))
    rng_for_model = np.random.RandomState(seed=random_seed)

    max_iter = param["max_iter"]
    changerate = param["changerate"]
    task_size = param["task_size"]
    validation = param["validation"]

    lr = param["lr"]
    initial_prior_var = param["initial_prior_var"]
    beta = param["beta"]
    independent = param["independent"]
    surrogate_initial_prior_path = param["surrogate_initial_prior_path"]

    diffusion = param["diffusion"]

    if surrogate_initial_prior_path is not None:
        if param["dataset_id"] == 0:
            surrogate_initial_prior_path = CIFAR10_SURROGATE_INITIAL_PRIOR_PATH_TEMPLATE \
                                            % param["surrogate_initial_prior_path"]
        elif param["dataset_id"] == 1:
            surrogate_initial_prior_path = SVHN_SURROGATE_INITIAL_PRIOR_PATH_TEMPLATE \
                                            % param["surrogate_initial_prior_path"]
        else:
            raise NotImplementedError

    if param["dataset_id"] == 0:
        datagen = LongTransformedCifar10Generator(
            rng=rng, changerate=changerate, 
            max_iter=max_iter, task_size=task_size,
            validation=validation)
    elif param["dataset_id"] == 1:
        datagen = LongTransformedSvhnGenerator(
            rng=rng, changerate=changerate, 
            max_iter=max_iter, task_size=task_size,
            validation=validation)
    else:
        raise NotImplementedError

    test_acc_path = bf(
        datagen=datagen,
        rng=rng_for_model,
        save_path=save_path,
        max_iter=max_iter,
        initial_prior_var=initial_prior_var,
        beta=beta,
        diffusion=diffusion,
        lr=lr,
        independent=independent,
        get_neural_net_with_prior=get_bayesian_neural_net_with_prior,
        param_layers_at_most=100,
        surrogate_initial_prior_path=surrogate_initial_prior_path)

    # evaluation procedure
    test_acc = np.load(test_acc_path)
    
    return np.average(test_acc)

import argparse
parser = argparse.ArgumentParser(description='Experiment configurations.')
parser.add_argument('--dataset', type=str, default='cifar10',
                    help='svhn, cifar10')
parser.add_argument('--validation', action='store_true')

if __name__ == '__main__':
    args = parser.parse_args()

    if args.dataset == 'svhn':
        params = svhn_params

        validation = args.validation
        params["validation"] = [validation]

        folder_name = ("./svhn_with_initial" 
            f'/bf_res'
            f'{"_test" if not validation else ""}'
            '/')

    elif args.dataset == 'cifar10':
        params = cifar10_params

        validation = args.validation
        params["validation"] = [validation]

        folder_name = ("./cifar10_with_initial" 
            f'/bf_res'
            f'{"_test" if not validation else ""}'
            '/')

    else:
        raise NotImplementedError

    os.makedirs(folder_name)


    hs = HyperparameterSearch(num_worker=1, first_gpu=0, num_gpu=1, 
                              save_dir=folder_name)

    best_param_list, params_list, res_list = hs.hyperparameter_optimization(
        train_and_eval, params)