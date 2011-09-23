#!/usr/bin/env python
"""
This function performs a transition state search with the "dimer method"

USAGE:
   paratools dimer --calculator <calculator_file> <geometry file> <start mode_vector file>

It needs at least three input files:
 * one containing the quantum chemical calculator
   (<calculator_file>) which is given via the parameter --calculator
 * one containing some kind of Cartesian geometry. This file (<geometry file>) should be
   ASE readable, meaning being in a format that ASE could understand (or be a gxfile having
   gx in its name)
 * one should contain a mode vector. This should be as near as possible to the expected
   negative eigenmode at the position specified by the geometry file. It can be given in internal
   coordinates (than each entry needs a new line) or in Cartesian coordinates (where each atom has
   a line with three entries).

GEOMETRIES AND COORDINATE SYSTEMS:

There are more options to the coordinate system choice (for example using internal coordinates for
optimization). To find more about them do:
   paratools dimer --help geometries

FURTHER OPTIONS:

There are some more variables specifying the way the dimer method run. Currently they are just handed over
to the dimer main program, so one could use them but the interface to them is not yet finished as
is the set of them. The defaults are currently similar to the ones given by ASE dimer, which follows a
very similar strategy. If it is wanted to change there something find out the name of the variable to change
in dimer module and add to your command:
  --<variable name> <new value>

Just to mention one: the maximum number of translation step defaults to a very large number. to reduce it
add to the paratools command:
  --max_translation <number of translation iterations>

So for example to have only 100 of them:
  --max_translation 100

Currently there are maximal 10 rotation steps per translation step allowed.
EXAMPLES:
Having in a directory the geometry file (POSCAR) POSCAR.start as well as the mode vector file MODE_START
and a valid caluclator file calc.py do to start a 20 translation steps dimer optimization:

  paratools dimer --calculator calc.py  --max_translation 20 POSCAR.start MODE_START

"""
from pts.io.read_inputs import get_geos, get_masked, from_params_file
from pts.io.read_COS import geo_params, info_geometries
from numpy import loadtxt
from pts.func import compose
from pts.qfunc import QFunc
from sys import exit, stderr

def read_dimer_input(rest):
    """
    This function is similar to the one for pathsearcher
    """
    #This variables will be needed afterwards anyway
    # independent of beeing given by user
    geo_dict = {"format" : None}
    add_param = {}
    paramfile = None
    zmatrix = []
    geo = None
    mode = None

    if "--help" in rest:
        if "geometries" in rest:
           info_geometries()
        else:
           print __doc__

        exit()


    for i in range(len(rest)):
        if rest == []:
            break

        # filter out all the options
        if rest[0].startswith("--"):
            o = rest[0][2:]
            a = rest[1]
            # filter out the special ones
            if o == "paramfile":
                # file containing parameters
                paramfile = file2str(a)
            elif o in ("zmatrix"):
                # zmatrix if given separate to the geometries
                zmatrix.append(a)
            elif o in geo_params:
                # only needed to build up the geometry
              if o in ("mask"):
                   # needed to build up the geometry and wanted for params output
                  geo_dict[o] = get_mask(a)
              elif o in ("cell", "pbc"):
                  geo_dict[o] = eval(a)
              else:
                  geo_dict[o] = a
            else:
                # suppose that the rest are setting parameters
                # currently we do not have a complet list of them
                add_param[o] = eval(a)
            rest = rest[2:]
        else:
            # This two files are needed any way: one geometry file and one
            # for the modevector, expect the geoemtry file to be given first
            if geo == None:
                # For reusing pathsearcher routines with several geoemtries for input
                geo = [ rest[0]]
            else:
                mode = rest[0]
            rest = rest[1:]

    default_params = {}

    if paramfile == None:
        params_dict = add_param
        geo_dict_dim = geo_dict
    else:
        # Use pathsearcher routine, it expects to get dictionary to check for
        # default parameter
        params_dict, geo_dict_dim = from_params_file(paramfile, default_params)
        params_dict.update(add_param)
        geo_dict_dim.update(geo_dict)

    zmat = None
    # also pathsearcher routines to build atoms object and internal to Cartesian
    # handle, the variables not used here would be required to ensure
    # shortest way between some pictures
    atoms, init_geo, funcart, __, __, __ = get_geos(geo, geo_dict_dim, zmatrix)
    # if a mask has been provided, some variables are not optimized
    funcart, init_geo = get_masked(funcart, atoms, geo_dict_dim, zmatrix == None, init_geo)

    # We have only one geometry here
    start_geo = init_geo[0]

    # Modevector either in internals (like direct from previous calculation with
    # dimer or pathsearcher) or external most certainly in Cartesian
    mode_cart = loadtxt(mode)
    try:
        # Test for Cartesian
        ma, mb = mode_cart.shape
        if mb == 3:
           # The functions build up so far, all provide this:
           init_mode = (funcart.pinv(funcart(start_geo) * 0.0001 * mode_cart) - start_geo) / 0.0001
           # init_mode will be normed correctly (after metric is set) lateron, here do
           # only roughly
        else:
           print >> stderr, "Error: illegal format for mode vector."
           print >> stderr, "Needs either internal coordinates or Cartesian coordinates."
           exit()
    except ValueError:
       # Needs to be in internal then
       assert (len(mode_cart) == len(start_geo))
       init_mode = mode_cart

    # Build up the qfunc, calculator is included in atoms already
    pes = compose(QFunc(atoms, calc = atoms.get_calculator()), funcart)

    #Attention inital mode need not be normed (and cannot as metric is not yet known)
    return pes, start_geo, init_mode, params_dict, atoms, funcart
