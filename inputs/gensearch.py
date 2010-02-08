#!/usr/bin/env python

import sys
import os
import aof
from aof.common import file2str
import ase
from numpy import zeros # temporary

name, params_file, mol_strings, init_state_vec, prev_results_file = aof.setup(sys.argv)

# TODO: setup circular re-naming to prevent accidental overwrites
logfile = open(name + '.log', 'w')
disk_result_cache = '%s.ResultDict.pickle' % name

# bring in custom parameters

extra_opt_params = dict()
params_file_str = file2str(params_file)
print params_file_str
exec(params_file_str)

# set up some objects
mi          = aof.MolInterface(mol_strings, params)
calc_man    = aof.CalcManager(mi, procs_tuple, to_cache=disk_result_cache, from_cache=prev_results_file)

# setup searcher i.e. String or NEB
if init_state_vec == None:
    init_state_vec = mi.reagent_coords

cos_type = cos_type.lower()
if cos_type == 'string':
    CoS = aof.searcher.GrowingString(init_state_vec, 
          calc_man, 
          beads_count,
          growing=False,
          parallel=True,
          reporting=logfile,
          max_sep_ratio=0.3)
elif cos_type == 'growingstring':
    CoS = aof.searcher.GrowingString(init_state_vec, 
          calc_man, 
          beads_count,
          growing=True,
          parallel=True,
          reporting=logfile,
          max_sep_ratio=0.3)
elif cos_type == 'neb':
    CoS = aof.searcher.NEB(init_state_vec, 
          calc_man, 
          spr_const,
          beads_count,
          parallel=True,
          reporting=logfile)
else:
    raise Exception('Unknown type: %s' % cos_type)


# callback function
def cb(x, tol=0.01):
    return aof.generic_callback(x, mi, CoS, params, tol=tol)

# print out initial path
cb(CoS.state_vec)

# hack to enable the CoS to print in cartesians, even if opt is done in internals
CoS.bead2carts = lambda x: mi.build_coord_sys(x).get_cartesians().flatten()

runopt = lambda: aof.runopt(opt_type, CoS, ftol, xtol, maxit, cb, maxstep=maxstep, extra=extra_opt_params)

# main optimisation loop
print runopt()

# get best estimate(s) of TS from band/string
tss = CoS.ts_estims()

a,b,c = CoS.path_tuple()
cs = mi.build_coord_sys(a[0])
import pickle
f = open("%s.path.pickle" % name, 'wb')
pickle.dump((a,b,c,cs), f)
f.close()

# print cartesian coordinates of all transition states that were found
print "Dumping located transition states"
for ts in tss:
    e, v = ts
    cs = mi.build_coord_sys(v)
    print "Energy = %.4f eV" % e
    print cs.xyz_str()


