#!/usr/bin/env python

import sys
from numpy.linalg import norm

from pts.tools.pathtools import PathTools, unpickle_path
from pts.tools.pathtools import read_path_fix, read_path_coords
from pts.searcher import new_abscissa
from pts.path import Path
from pts.common import make_like_atoms
import numpy as np
from pydoc import help
from os import path, mkdir, chdir, getcwd, system
import pts.metric as mt

def main(argv):
    """
    Takes a path file and estimates the transition states from it
    path file can be in path.pickle format or alterantively with the
    needed values by separate user readable files.

    gives back the transition states (and the modevectors) for different
    transition state estimates

    first argument is the path.pickle or internal coordinate file to read in
    (or --help to get this help text)

    One can choose which transtition state estimates are to be generated
    by giving the numbers related to the wanted ones (default is all of them)
    1  : highest
    2  : Spline
    3  : Spline and average
    4  : Spline and cubic
    5  : Three points
    6  : Bell method

    Arguments for different read in fo input: (if used instead of path.pickle file
          with geometries one has to provide a coordinate file
    --s  symbolfile energyfile forcefile : This three files are needed in any case
          if the other way of input is choosen. Symbolfile contains all atom symbols
          energyfile and forcefile the energies/forces to the given geometries from
          coordinates file
    --a abscissafile: the abscissa to the coordinates is optional, string calculations
          use some, some others like neb do not have them at all, if the calcualtion
          of the path had been one with abscissa it is preferable to give them here
    --zmat zmatfile : give the same zmatfiles (each with its own --zmat) as in the
          path calculation, only this way the internal coordinates can be interpreted
          correctly
    --mask maskfile geo_raw: only variables set to True in maskfile are supposed
          to be given in coordinate files, all others are extracted from geo_raw

    Other possible arguments:
    --p : print the resulting transition state estimates (is also the default
          if no other argument is set
    --m : print also available mode vector estimates
          (can also be given by any combination of p and m)
    --c : for comparing the strings with the previous ones
          the output are relevant data from the approximated string
          the --p option is set to false by default
          if the next argument is a file name (for a logfile)
          the program search in it for data to compare the results
          from

    All output goes by default to the standard output
    """

    printwithmodes = False
    printvectors = True
    wanted = []
    fileout = "-"
    fileout2 = None
    comparepath = False
    dump = False


    # for other way of input:
    zmats = []
    mask = None
    maskgeo = None
    abcis = None
    symbfile = None
    energies = None
    forces = None


    # structure of inputs, has to be improved later
    # The --help option is handled seperatly
    # The first input argument has to be the path.pickle object
    if argv[0] == '--help':
        print main.__doc__
        sys.exit()
    else:
        try:
            f_ts = argv[0]
        except:
            print "ERROR: No path file found to read input from"
            print "First argument of call must be a path.pickle object"
            print "Usage of this function:"
            print main.__doc__
            sys.exit()

    if len(argv)>1:
        argv = argv[1:]
        # cycle over all the remaining arguments, they
        # are moved to the beginning, so argv[0] is always the
        # first argument not yet interpreted
        for i in range(len(argv)):
            if argv[0].startswith('--'):
                # the options start with --
                # sometimes the following argument(s) belong
                # also to the option and are read in also
                arg = argv[0][2:]
                if arg in ['m','pm', 'mp'] :
                     printwithmodes = True
                     printvectors = True
                elif arg == 'p':
                     printvectors = True
                elif arg == 'd':
                     print "Only special output"
                     dump = True
                elif arg == "s":
                    symbfile = argv[1]
                    energies = argv[2]
                    forces = argv[3]
                    argv = argv[3:]
                elif arg =="zmat":
                    zmats.append(argv[1])
                    argv = argv[1:]
                elif arg == "mask":
                    mask = argv[1]
                    maskgeo = argv[2]
                    argv = argv[2:]
                elif arg == "a":
                   abcis = argv[1]
                   argv = argv[1:]
                elif arg == 'c':
                     comparepath = True
                     printvectors = False
                     filecomp = None
                     try:
                         filecomp =  open(argv[1], "r")
                         argv = argv[1:]
                         numinfile = int(argv[1])
                         argv = argv[1:]
                     except:
                         numinfile = -1
                argv = argv[1:]
            else:
                try:
                   # the arguments not starting with --, may be the number
                   # of the transition state approximation wanted
                   for a in argv:
                       wanted.append(int(a))
                except:
                    #FIXME: is it okay to ignore everything else?
                    pass
                argv = argv[len(wanted):]
            if argv == []:
                break

    # if none is choosen, all are selected
    if wanted == []:
        wanted = [1, 2, 3, 4, 6]

    if symbfile == None:
        coord_b, energy_b, gradients_b, tangents, posonstring, symbols, trafo = unpickle_path(f_ts) # v2
    else:
        symbols, trafo = read_path_fix( symbfile, zmats, mask, maskgeo )
        coord_b, posonstring, energy_b, gradients_b = read_path_coords(f_ts, abcis, energies, forces)

    at_object = (symbols, trafo)
    # calculate the (wanted) estimates
    estms, stx2 = esttsandmd(coord_b, energy_b, gradients_b, at_object, wanted)
    # show the result
    if printvectors:
        if dump:
            print_estimatesdump(estms, at_object)
        else:
            print_estimates(estms, at_object, printwithmodes)
    if comparepath:
        newpath = Path(coord_b, stx2)
        oldpath = Path(coord_b)
        comparepathes(oldpath, newpath, gradients_b, numinfile, filecomp)

def esttsandmd(coord_b, energy_b, gradients_b, at_object, \
               ts_wanted = [1, 2, 3, 4, 5, 6] ):
    """
    calculating of wanted TS-estimates and their modes
    This is done in two different ways of parametrizing the string:
    First as it is done in the pathway tools
    Second with the spacing gotten from the PathRepresentation object
    (should be the same as opptimized)
    """

    # in this variable the estimates will be stored as
    # ( name, ts-estimate object, (modename, modevec) * number of modeapprox
    ts_all = []

    numbeads = len(energy_b)
    #ATTENTION: this needs to be consistent to the way abscissas are build for PathRepresentation
    startx =  new_abscissa(coord_b, mt.metric)

    # with the additional startvalue startx the same as for the other path
    path2 = PathTools(coord_b, energy_b, gradients_b, startx)
    statex2 = path2.steps

    estfrompathfirst(path2, ts_all, at_object, " with given distance by string", ts_wanted )

    return (ts_all, statex2)


def estfrompathfirst(pt, ts_sum, cs, addtoname, which):
    """
    Some approximations are independent of the path,
    thus this wrapper calculates all, while
    estfrompath only calculates the one depending on a path
    """
    ts_est = []
    __, trafo = cs
    #cs_c = cs.copy()
    if 1 in which:
        ts_est.append(('Highest', pt.ts_highest()[-1]))
    if 5 in which:
        ts_int = pt.ts_threepoints()
        if len(ts_int) > 0:
            ts_est.append(('Three points', ts_int[-1]))
    if 6 in which:
        ts_int = pt.ts_bell()
        if len(ts_int) > 0:
            ts_est.append(('Bell Method',ts_int[-1]))
    # generates modevectors to the given TS-estimates
    for name, est in ts_est:
         energy, coords, s0, s1,s_ts,  l, r = est
         modes =  pt.modeandcurvature(s_ts, l, r, trafo)
         addforces = neighborforces(pt, l, r)
         ts_sum.append((name, est, modes, addforces))

    estfrompath(pt, ts_sum, cs, addtoname, which)



def estfrompath(pt2, ts_sum, cs, addtoname, which ):
    """
    Calculates the TS-estimates and their modevectors
    which are choosen and put them back together
    """
    ts_est = []
    __, trafo = cs
    #cs_c = cs.copy()
    if 2 in which:
        ts_int = pt2.ts_spl()
        if len(ts_int) > 0:
            ts_est.append(('Spline only',ts_int[-1]))
    if 3 in which:
        ts_int = pt2.ts_splavg()
        if len(ts_int) > 0:
             ts_est.append(('Spline and average', ts_int[-1]))
    if 4 in which:
        ts_int = pt2.ts_splcub()
        if len(ts_int) > 0:
            ts_est.append(('Spling and cubic', ts_int[-1]))

    # generates modevectors to the given TS-estimates
    for name, est in ts_est:
         energy, coords, s0, s1,s_ts,  l, r = est
         modes =  pt2.modeandcurvature(s_ts, l, r, trafo)
         addforces = neighborforces(pt2, l, r)
         ts_sum.append((name + addtoname , est, modes, addforces))

def comparepathes(oldpath, path, gradients, num, file):

    print "Data of new path"
    xs, project = projpath(path, gradients)

    print "Data of old path"
    xso, projecto = projpath(oldpath, gradients)

    if not file==None:
        print
        print "==========================================================="
        print "      Comparision of the different path approximations:"
        print "==========================================================="
        if num < 0 :
            num = 0
        rightnum = False
        for line in file:
             if line.startswith('Chain of States Summary'):
                 fields = line.split()
                 if str(num) in fields:
                     rightnum = True
                 else:
                     rightnum = False
             if rightnum:
                 if line.startswith('Para Forces'):
                     fields = line.split()
                     dataline = []
                     datapoints = (len(fields) - 2) / 2
                     for i in range(datapoints):
                         dataline.append(float(fields[3 +2 * i]))
                     print "Difference in the projection of the force on the string:"
                     diff1 = [project[i] - dataline[i] for i in range(len(dataline))]
                     diff2 = [projecto[i] - dataline[i] for i in range(len(dataline))]
                     diff3 = [projecto[i] - project[i] for i in range(len(dataline))]
                     print "the values from the path approximations (old/new)  and the values stored in the logfile"
                     for i in range(len(dataline)):
                          print "%-d    %-12.7f  %-12.7f | %-12.7f" %  (i, projecto[i], project[i], dataline[i])
                     print "The differences are (logfile to old/new):"
                     for i in range(len(dataline)):
                          print "%-d    %-12.7f  %-12.7f " % (i, diff2[i], diff1[i])
                     print "The differences between the projections:"
                     print "old - new"
                     differ = '   '.join(['%12.7f' % i for i in diff3])
                     print differ
                 if line.startswith('Bead Path Position'):
                     fields = line.split()
                     dataline = []
                     datapoints = (len(fields) - 3) / 2
                     for i in range(datapoints):
                         dataline.append(float(fields[4 +2 * i]))
                     print "Difference of the stored bead positions (to old/new):"
                     diff1 = [xso[i]/xso[-1] - dataline[i] for i in range(len(dataline))]
                     diff2 = [xs[i] - dataline[i] for i in range(len(dataline))]
                     differ1 = '   '.join(['%12.7f' % i for i in diff1])
                     differ2 = '   '.join(['%12.7f' % i for i in diff2])
                     print differ1
                     print differ2


def projpath(path, gradients):
    print path.get_nodes()
    xs, ys = path.get_nodes()
    print xs
    print "Forces on String"
    project = []
    for i, x in enumerate(xs):
         grad = gradients[i].flatten()
         mode = -path.fprime(x).flatten()
         mode = mode / norm(mode)
         proj = np.dot(mode, grad)
         print proj
         project.append(proj)
    return xs, project


def neighborforces(pt, il, ir):
    paral, perpl = oneneighb(pt, il)
    parar, perpr = oneneighb(pt, ir)
    return (paral, perpl, parar, perpr)

def oneneighb(pt, i):

    xs, ys = pt.xs.get_nodes()
    mode = -pt.xs.fprime(xs[i]).flatten()
    mode = mode / norm(mode)
    fr = pt.gradients[i].flatten()
    para, perp = para_perp_forces(mode, fr)
    perprms = np.sqrt(np.dot(perp.flatten(), perp.flatten()))
    return para, perprms

def getforces(ts_sum, cs, file, reloadfile, file2, dump):
    """
    Calculates the energy and the forces of the ts_approximates
    and makes the dot products with all the modevectors for the forces
    """

    # there are different possibilities whereto the output should go
    # default is standart output for all
    # The forces and Energies calculated may be stroed seperately
    if file == "-":
        write = sys.stdout.write
    else:
        write = open(file,"w").write
        write("Forces calculated for the different transition state estimates\n")
        write("Units are eV/Angstrom\n")

    if file2 == None:
        write2 = sys.stdout.write
    else:
        write2 = open(file2,"w").write

    if dump:
        write2(" E in eV: calc, appr., diff; f_max; para forces in eV/A: bead_l, at approx, bead_r;  perp forces in eV/A: bead_l, at approx, bead_r\n")

    # For all the geometries we have do:
    for i, (name, est, modes, addforces) in enumerate(ts_sum):
        # get geometries, string informations and approximated energy
        # form the estimated storage
        energy, coords, s0, s1,s_ts,  l, r = est
        # put the geomtry in the working "faked" atoms object
        cs.set_internals(coords)

        for1, for2, for3, for4 = addforces
        atnames = cs.get_chemical_symbols()
        trueE = None
        cartforces = None

        # Maybe the forces and energies have been stored before
        #Then they only have to be reread
        # Note that this function looks if the wanted approximation is in
        # the file, it decides for each of them seperatly
        # But it does not check if the file is realy for the current molecule
        if not reloadfile == None:
            trueE, cartforces = reloadfande(reloadfile, name, len(atnames))
            # we also want the forces in internal coordinates (especially as there
            # the constraints are used)
            forces = transformforces(cartforces, cs)

        # if the energies and forces have not been stored, they have to be calculated
        # here, use for it the atoms object
        if trueE == None:
            wopl = getcwd()
            wx = "mode%i" % i
            if not path.exists(wx):
               mkdir(wx)
            chdir(wx)
            trueE = cs.get_potential_energy()
            cartforces = cs.get_cartforces()
            forces = cs.get_forces()
            chdir(wopl)

        cartforces = np.asarray(cartforces)

        if dump:
            projection = []
            for  namemd, modevec in modes:
                 projection.append(np.dot(np.asarray(modevec).flatten(), np.asarray(cartforces).flatten()))
            para, perp = para_perp_forces( np.asarray(modevec).flatten(), np.asarray(cartforces).flatten() )
            force2rms = np.sqrt(np.dot(perp.flatten(), perp.flatten()))
            write2("  %16.9e  %16.9e  %16.9e   %16.9e   %16.9e   %16.9e  %16.9e  %16.9e   %16.9e   %16.9e\n" % ( trueE, energy,  (energy - trueE), abs(forces).max(),for1, projection[2], for3 , for2, force2rms, for4))
            continue


        # output for each of the approximations
        write("Looking at the approximation %s\n" % name)
        write("The energy is: %16.9e\n" % trueE)
        for num, force_n in enumerate(cartforces):
            write(_tostr_forces(atnames[num], force_n))

        write2("-------------------------------------------------------------------\n" )
        write2("The observations of energy and forces for the case %s are:\n" % name)
        write2("The energies are approximated %16.9e and true was %19.6e\n" % (energy, trueE))
        write2("The difference in Energy (approx - true) is: %16.9e\n" % (energy - trueE))
        write2("The   maximum  internal force component  is: %16.9e\n" % abs(forces).max() )
        write2("The   maximum Cartesian force component  is: %16.9e\n" % abs(cartforces.flatten()).max() )

        write2("\nThe force component projected on the modevectors\n")
        write2("            modevector     |      value\n")

        para = None
        perp = None
        for namemd, modevec in modes:
        #     write2("       for the modevector %s\n" % namemd)
             projection = np.dot(np.asarray(modevec).flatten(), np.asarray(cartforces).flatten())
        #     write2("       has the value:     %16.9e\n" % projection)
             write2("  %24s | %16.9e\n" % (namemd, projection))
             if namemd == "frompath":
                para, perp = para_perp_forces( np.asarray(modevec).flatten(), np.asarray(cartforces).flatten() )
                force2rms = np.sqrt(np.dot(perp.flatten(), perp.flatten()))

        if not para == None:
            write2("\n    The para/perp forces are:\n")
            write2("              at approximation,                      bead before,                          bead after\n")
            write2("  %16.9e / %16.9e   %16.9e / %16.9e   %16.9e / %16.9e\n" % (para,force2rms , for1, for2, for3, for4 ))


def para_perp_forces( m, f):
    if not ( abs( np.dot(m, m) - 1) < 1e-10):
        m /= np.sqrt(np.dot(m,m))
    para = np.dot(m, f)
    perp = f - para * m
    return para, perp

def _tostr_forces(nam, force):
    force = tuple( map(float, force) )
    fields = (nam,) + force

    return ( "%s      %16.9e %16.9e %16.9e\n" % fields )

def _parse_force(lines, max):
     for i, line in enumerate(lines):
         if i >= max:
             return
         grads = _parse_f1(line)
         yield grads

def _parse_f1(line):
     fields = line.split()
     grad = map(float, fields[1:4])
     return grad

def transformforces(c_forces, cs):
     forces_flat = np.asarray(c_forces)
     forces_flat = forces_flat.flatten()
     transform_matrix, errors = cs.get_transform_matrix(cs._mask(cs._coords))
     forces_coord_sys = np.dot(transform_matrix, forces_flat)

     forces_coord_sys = cs.apply_constraints(forces_coord_sys)
     make_like_atoms(forces_coord_sys)
     return forces_coord_sys

def reloadfande(file, name, num):
     lines = open(file)
     found = False
     energy = None
     grads = None
     for  line in lines:
         if name in line:
              found = True
              break
     if found:
         fields = lines.next().split()
         energy = float(fields[3])
         grads = list(_parse_force(lines, num))
     return energy, grads


def print_estimates(ts_sum, cs, withmodes = False ):
     """
     Prints the transition state estimates with their geometry
     in xyz-style, and their mode vectors if wanted
     """
     __, trafo = cs
     print "==================================================="
     print "printing all available transition state estimates"
     print "---------------------------------------------------"
     for name, est, modes, addforces in ts_sum:
          print "TRANSITION STATE ESTIMATE:", name
          energy, coords, s0, s1,s_ts,  l, r = est
          print "Energy was approximated as:", energy
          print "This gives the positition:"
          print trafo(coords)
          print
          if withmodes:
              print "The possible modes are:"
              for namemd, modevec in modes:
                   print "Approximation of mode in way ", namemd
                   for line in modevec:
                       print "   %12.8f  %12.8f  %12.8f" % (line[0], line[1], line[2])

              print

def print_estimatesdump(ts_sum, cs ):
     """
     Prints all the geometries as a (jmol) xyz file
     """
     symbs, trafo = cs
     print
     for name, est, modes, addforces in ts_sum:
          numats = len(symbs)
          print numats
          energy, coords, s0, s1,s_ts,  l, r = est
          print "Energy was approximated as:", energy
          carts = trafo(coords)
          for s, c in zip(symbs, carts):
              x, y, z = c
              print '%-2s %22.15f %22.15f %22.15f' % (s, x, y, z)



if __name__ == "__main__":
    main(sys.argv[1:])


