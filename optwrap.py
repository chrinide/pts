"""Provides a uniform interface to a variety of optimisers."""

from aof.cosopt.lbfgsb import fmin_l_bfgs_b
from scipy.optimize import fmin_cg

import ase
import aof
from aof.searcher import MustRegenerate

__all__ = ["opt"]

def runopt(name, CoS, tol, maxit, callback, maxstep=0.2):
    names = ['scipy_lbfgsb', 'ase_lbfgs', 'ase_fire', 'quadratic_string', 'ase_scipy_cg', 'ase_scipy_lbfgsb']
    assert name in names

    
    while True:
        try:
            runopt_inner(name, CoS, tol, maxit, callback, maxstep=0.2)
        except MustRegenerate:
            CoS.update_path()
            print "Optimisation RESTARTED (respaced)"
            continue

        if CoS.grow_string():
            print "Optimisation RESTARTED (string grown)"
        else:
            break

def runopt_inner(name, CoS, tol, maxit, callback, maxstep=0.2):

    if name == 'scipy_lbfgsb':
        opt, energy, dict = fmin_l_bfgs_b(CoS.obj_func,
                                  CoS.get_state_as_array(),
                                  fprime=CoS.obj_func_grad,
                                  callback=callback,
                                  pgtol=tol,
                                  factr=10, # stops when step is < factr*machine_precision
                                  maxfun=maxit, maxstep=maxstep)
        return dict

    elif name[0:4] == 'ase_':

        if name == 'ase_lbfgs':
            opt = ase.LBFGS(CoS, maxstep=maxstep)
        elif name == 'ase_fire':
            opt = ase.FIRE(CoS)
        elif name == 'ase_scipy_cg':
            opt = ase.SciPyFminCG(CoS)
        elif name == 'ase_scipy_lbfgsb':
            opt = aof.cosopt.SciPyFminLBFGSB(CoS, alpha=200)
        else:
            assert False, ' '.join(["Unrecognised algorithm", name, "not in"] + names)

        # attach optimiser to print out each step in
        opt.attach(lambda: callback(None), interval=1)
        opt.run(fmax=tol, steps=maxit)
        x_opt = CoS.state_vec
        return None

    elif name == 'quadratic_string':
        gqs = aof.searcher.QuadraticStringMethod(CoS, callback=callback, update_trust_rads = True)
        opt = gqs.opt()
    else:
        assert False, ' '.join(["Unrecognised algorithm", name, "not in"] + names)

