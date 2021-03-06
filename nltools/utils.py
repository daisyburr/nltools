'''
NeuroLearn Utilities
====================

handy utilities.

'''
__all__ = ['get_resource_path',
            'get_anatomical',
            'set_algorithm',
            'spm_hrf',
            'glover_hrf',
            'spm_time_derivative',
            'glover_time_derivative',
            'spm_dispersion_derivative',
            'attempt_to_import',
            'all_same',
            'concatenate',
            '_bootstrap_apply_func',
            'set_decomposition_algorithm'
            ]
__author__ = ["Luke Chang"]
__license__ = "MIT"

from os.path import dirname, join, sep as pathsep
import nibabel as nib
import importlib
import os
from sklearn.pipeline import Pipeline
from scipy.stats import gamma
import numpy as np
import collections
from types import GeneratorType

def get_resource_path():
    """ Get path to nltools resource directory. """
    return join(dirname(__file__), 'resources') + pathsep

def get_anatomical():
    """ Get nltools default anatomical image.
        DEPRECATED. See MNI_Template and resolve_mni_path from nltools.prefs
    """
    return nib.load(os.path.join(get_resource_path(),'MNI152_T1_2mm.nii.gz'))

def set_algorithm(algorithm, *args, **kwargs):
    """ Setup the algorithm to use in subsequent prediction analyses.

    Args:
        algorithm: The prediction algorithm to use. Either a string or an
                    (uninitialized) scikit-learn prediction object. If string,
                    must be one of 'svm','svr', linear','logistic','lasso',
                    'lassopcr','lassoCV','ridge','ridgeCV','ridgeClassifier',
                    'randomforest', or 'randomforestClassifier'
        kwargs: Additional keyword arguments to pass onto the scikit-learn
                clustering object.

    Returns:
        predictor_settings: dictionary of settings for prediction

    """

    # NOTE: function currently located here instead of analysis.py to avoid circular imports

    predictor_settings = {}
    predictor_settings['algorithm'] = algorithm

    def load_class(import_string):
        class_data = import_string.split(".")
        module_path = '.'.join(class_data[:-1])
        class_str = class_data[-1]
        module = importlib.import_module(module_path)
        return getattr(module, class_str)

    algs_classify = {
        'svm': 'sklearn.svm.SVC',
        'logistic': 'sklearn.linear_model.LogisticRegression',
        'ridgeClassifier': 'sklearn.linear_model.RidgeClassifier',
        'ridgeClassifierCV': 'sklearn.linear_model.RidgeClassifierCV',
        'randomforestClassifier': 'sklearn.ensemble.RandomForestClassifier'
        }
    algs_predict = {
        'svr': 'sklearn.svm.SVR',
        'linear': 'sklearn.linear_model.LinearRegression',
        'lasso': 'sklearn.linear_model.Lasso',
        'lassoCV': 'sklearn.linear_model.LassoCV',
        'ridge': 'sklearn.linear_model.Ridge',
        'ridgeCV': 'sklearn.linear_model.RidgeCV',
        'randomforest': 'sklearn.ensemble.RandomForest'
        }

    if algorithm in algs_classify.keys():
        predictor_settings['prediction_type'] = 'classification'
        alg = load_class(algs_classify[algorithm])
        predictor_settings['predictor'] = alg(*args, **kwargs)
    elif algorithm in algs_predict:
        predictor_settings['prediction_type'] = 'prediction'
        alg = load_class(algs_predict[algorithm])
        predictor_settings['predictor'] = alg(*args, **kwargs)
    elif algorithm == 'lassopcr':
        predictor_settings['prediction_type'] = 'prediction'
        from sklearn.linear_model import Lasso
        from sklearn.decomposition import PCA
        predictor_settings['_lasso'] = Lasso()
        predictor_settings['_pca'] = PCA()
        predictor_settings['predictor'] = Pipeline(
                            steps=[('pca', predictor_settings['_pca']),
                            ('lasso', predictor_settings['_lasso'])])
    elif algorithm == 'pcr':
        predictor_settings['prediction_type'] = 'prediction'
        from sklearn.linear_model import LinearRegression
        from sklearn.decomposition import PCA
        predictor_settings['_regress'] = LinearRegression()
        predictor_settings['_pca'] = PCA()
        predictor_settings['predictor'] = Pipeline(
                            steps=[('pca', predictor_settings['_pca']),
                            ('regress', predictor_settings['_regress'])])
    else:
        raise ValueError("""Invalid prediction/classification algorithm name.
            Valid options are 'svm','svr', 'linear', 'logistic', 'lasso',
            'lassopcr','lassoCV','ridge','ridgeCV','ridgeClassifier',
            'randomforest', or 'randomforestClassifier'.""")

    return predictor_settings

def set_decomposition_algorithm(algorithm, n_components=None, *args, **kwargs):
    """ Setup the algorithm to use in subsequent decomposition analyses.

    Args:
        algorithm: The decomposition algorithm to use. Either a string or an
                    (uninitialized) scikit-learn decomposition object.
                    If string must be one of 'pca','nnmf', ica','fa'
        kwargs: Additional keyword arguments to pass onto the scikit-learn
                clustering object.

    Returns:
        predictor_settings: dictionary of settings for prediction

    """

    # NOTE: function currently located here instead of analysis.py to avoid circular imports

    def load_class(import_string):
        class_data = import_string.split(".")
        module_path = '.'.join(class_data[:-1])
        class_str = class_data[-1]
        module = importlib.import_module(module_path)
        return getattr(module, class_str)

    algs = {
        'pca': 'sklearn.decomposition.PCA',
        'ica': 'sklearn.decomposition.FastICA',
        'nnmf': 'sklearn.decomposition.NMF',
        'fa': 'sklearn.decomposition.FactorAnalysis'
        }

    if algorithm in algs.keys():
        alg = load_class(algs[algorithm])
        alg = alg(n_components, *args, **kwargs)
    else:
        raise ValueError("""Invalid prediction/classification algorithm name.
            Valid options are 'pca','ica', 'nnmf', 'fa'""")
    return alg

# The following are nipy source code implementations of the hemodynamic response function HRF
# See the included nipy license file for use permission.

def _gamma_difference_hrf(tr, oversampling=16, time_length=32., onset=0.,
                        delay=6, undershoot=16., dispersion=1.,
                        u_dispersion=1., ratio=0.167):
    """ Compute an hrf as the difference of two gamma functions
    Parameters
    ----------
    tr: float, scan repeat time, in seconds
    oversampling: int, temporal oversampling factor, optional
    time_length: float, hrf kernel length, in seconds
    onset: float, onset of the hrf
    Returns
    -------
    hrf: array of shape(length / tr * oversampling, float),
         hrf sampling on the oversampled time grid
    """
    dt = tr / oversampling
    time_stamps = np.linspace(0, time_length, float(time_length) / dt)
    time_stamps -= onset / dt
    hrf = gamma.pdf(time_stamps, delay / dispersion, dt / dispersion) - \
        ratio * gamma.pdf(
        time_stamps, undershoot / u_dispersion, dt / u_dispersion)
    hrf /= hrf.sum()
    return hrf


def spm_hrf(tr, oversampling=16, time_length=32., onset=0.):
    """ Implementation of the SPM hrf model.

    Args:
        tr: float, scan repeat time, in seconds
        oversampling: int, temporal oversampling factor, optional
        time_length: float, hrf kernel length, in seconds
        onset: float, onset of the response

    Returns:
        hrf: array of shape(length / tr * oversampling, float),
            hrf sampling on the oversampled time grid

    """

    return _gamma_difference_hrf(tr, oversampling, time_length, onset)


def glover_hrf(tr, oversampling=16, time_length=32., onset=0.):
    """ Implementation of the Glover hrf model.

    Args:
        tr: float, scan repeat time, in seconds
        oversampling: int, temporal oversampling factor, optional
        time_length: float, hrf kernel length, in seconds
        onset: float, onset of the response

    Returns:
        hrf: array of shape(length / tr * oversampling, float),
            hrf sampling on the oversampled time grid

    """

    return _gamma_difference_hrf(tr, oversampling, time_length, onset,
                                delay=6, undershoot=12., dispersion=.9,
                                u_dispersion=.9, ratio=.35)


def spm_time_derivative(tr, oversampling=16, time_length=32., onset=0.):
    """ Implementation of the SPM time derivative hrf (dhrf) model.

    Args:
        tr: float, scan repeat time, in seconds
        oversampling: int, temporal oversampling factor, optional
        time_length: float, hrf kernel length, in seconds
        onset: float, onset of the response

    Returns:
        dhrf: array of shape(length / tr, float),
              dhrf sampling on the provided grid

    """

    do = .1
    dhrf = 1. / do * (spm_hrf(tr, oversampling, time_length, onset + do) -
                      spm_hrf(tr, oversampling, time_length, onset))
    return dhrf

def glover_time_derivative(tr, oversampling=16, time_length=32., onset=0.):
    """Implementation of the flover time derivative hrf (dhrf) model.

    Args:
        tr: float, scan repeat time, in seconds
        oversampling: int, temporal oversampling factor, optional
        time_length: float, hrf kernel length, in seconds
        onset: float, onset of the response

    Returns:
        dhrf: array of shape(length / tr, float),
              dhrf sampling on the provided grid

    """

    do = .1
    dhrf = 1. / do * (glover_hrf(tr, oversampling, time_length, onset + do) -
                      glover_hrf(tr, oversampling, time_length, onset))
    return dhrf

def spm_dispersion_derivative(tr, oversampling=16, time_length=32., onset=0.):
    """Implementation of the SPM dispersion derivative hrf model.

    Args:
        tr: float, scan repeat time, in seconds
        oversampling: int, temporal oversampling factor, optional
        time_length: float, hrf kernel length, in seconds
        onset: float, onset of the response

    Returns:
        dhrf: array of shape(length / tr * oversampling, float),
              dhrf sampling on the oversampled time grid

    """

    dd = .01
    dhrf = 1. / dd * (_gamma_difference_hrf(tr, oversampling, time_length,
                                           onset, dispersion=1. + dd) -
                      spm_hrf(tr, oversampling, time_length, onset))
    return dhrf

def isiterable(obj):
    ''' Returns True if the object is one of allowable iterable types. '''
    return isinstance(obj, (list, tuple, GeneratorType))

module_names = {}
Dependency = collections.namedtuple('Dependency', 'package value')

def attempt_to_import(dependency, name=None, fromlist=None):
    if name is None:
        name = dependency
    try:
        mod = __import__(dependency, fromlist=fromlist)
    except ImportError:
        mod = None
    module_names[name] = Dependency(dependency, mod)
    return mod

def all_same(items):
    return np.all(x == items[0] for x in items)

def concatenate(data):
    '''Concatenate a list of Brain_Data() or Adjacency() objects'''

    if not isinstance(data, list):
        raise ValueError('Make sure you are passing a list of objects.')

    if all([type(x) for x in data]):
        # Temporarily Removing this for circular imports (LC)
        # if not isinstance(data[0], (Brain_Data, Adjacency)):
        #     raise ValueError('Make sure you are passing a list of Brain_Data'
        #                     ' or Adjacency objects.')

        out = data[0].__class__()
        for i in data:
            out = out.append(i)
    else:
        raise ValueError('Make sure all objects in the list are the same type.')
    return out

def _bootstrap_apply_func(data, function, *args, **kwargs):
    '''Bootstrap helper function. Sample with replacement and apply function'''
    data_row_id = range(data.shape()[0])
    new_dat = data[np.random.choice(data_row_id,
                                   size=len(data_row_id),
                                   replace=True)]
    return getattr(new_dat, function)( *args, **kwargs)
