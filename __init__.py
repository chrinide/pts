import searcher

class MustRegenerate(Exception):
    """Used to force the optimiser to exit if bead spacing has become uneven."""
    pass

class MustRestart(Exception):
    """Used to force the optimiser to exit in certain situations."""
    pass

class MaxIterations(Exception):
    """Used to force the optimiser to exit if max no of iterations has been exceeded."""
    pass

class Converged(Exception):
    """Used to force convergence."""
    pass

def cleanup(gs):
    """Perform error checking and other stuff on an environment used to run
    a search."""

    # empty for the time being
    pass

class UsageException(Exception):
    pass

def usage(n):
    print "Usage: " + n + ": --params file.py [--path initial_path.txt] [--load previous_run.pickle] reagent1.xyz, reagent2.xyz, ..."

def setup(argv):

    """Deal with command line arguments"""

    import os
    from pts.common import file2str
    import getopt
    from numpy import array, ndarray

    execname = argv[0]
    argv = argv[1:]

    init_state_vec = None
    params_file = None
    prev_results_file = None

    overrides = ""
    try:
        opts, reagents = getopt.getopt(argv, "h", ["params=", "path=", "load=", "help", "override="])
        for o, a in opts:
            if o in ("-h", "--help"):
                usage(execname)
                return 0
            elif o in ("--params"):
                params_file = a
            elif o in ("--load"):
                prev_results_file = a

            elif o in ("--override"):
                overrides += a + "\n"

            elif o in ("--path"):
                init_state_vec = eval(file2str(a))
                t = type(init_state_vec)
                if init_state_vec != None and t != ndarray:
                    raise UsageException("Object from %s had type %s" % (a, str(t)))

            else:
                raise UsageException("Unrecognised: " + o)

        if params_file == None:
            raise UsageException("You must supply a parameters file.")

        if len(reagents) < 2:
            raise UsageException("You must supply at least two reagents")

        mol_strings = [file2str(f) for f in reagents]
            
    except UsageException, e:
        usage(execname)
        exit(1)


    inputdir = os.path.dirname(reagents[0])
    names = [os.path.splitext(f)[0] for f in reagents]
    names = [os.path.basename(f) for f in reagents]
    name = "_to_".join(names) + "_with_" + os.path.splitext(os.path.basename(params_file))[0]

    return name, params_file, mol_strings, init_state_vec, prev_results_file, overrides, inputdir


