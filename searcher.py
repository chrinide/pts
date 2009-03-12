#!/usr/bin/python

from numpy import *
from scipy import *
from scipy import interpolate
import Gnuplot, Gnuplot.PlotItems, Gnuplot.funcutils
import tempfile, os
import logging
import copy
import pickle

logger = logging.getLogger("searcher.py")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

import scipy.integrate

print "\n\nBegin Program..." 


class QCDriver:
    def __init__(self, dimension):
        self.dimension = dimension

    def gradient(self, a):
        return (-1)

    def energy(self, a):
        return (-1)

"""def g(a):
    x = a[0]
    y = a[1]
    dzdx = 4*x**3 - 3*80*x**2 + 2*1616*x + 2*2*x*y**2 - 2*8*y*x - 80*y**2 
    dzdy = 2*2*x**2*y - 8*x**2 - 2*80*x*y + 2*1616*y + 4*y**3 - 3*8*y**2
    return array([dzdy, dzdx])

def e(a):
    x = a[0]
    y = a[1]
    z = (x**2 + y**2) * ((x - 40)**2 + (y - 4) ** 2)
    return (z)
"""

class GaussianPES(QCDriver):
    def __init__(self):
        QCDriver.__init__(self,2)

    def energy(self, v):
        x = v[0]
        y = v[1]
        return (-exp(-(x**2 + y**2)) - exp(-((x-3)**2 + (y-3)**2)) + 0.01*(x**2+y**2) - 0.3*exp(-((x-1)**2 + (y-2)**2)))

    def gradient(self, v):
        x = v[0]
        y = v[1]
        dfdx = 2*x*exp(-(x**2 + y**2)) + (2*x - 6)*exp(-((x-3)**2 + (y-3)**2)) + 0.02*x + 0.3*(2*x-2)*exp(-((x-1)**2 + (y-2)**2))
        dfdy = 2*y*exp(-(x**2 + y**2)) + (2*y - 6)*exp(-((x-3)**2 + (y-3)**2)) + 0.02*y + 0.3*(2*y-4)*exp(-((x-1)**2 + (y-2)**2))

        return array((dfdx,dfdy))

class GaussianPES2(QCDriver):
    def __init__(self):
        QCDriver.__init__(self,2)

    def energy(self, v):
        x = v[0]
        y = v[1]
        return (-exp(-(x**2 + 0.2*y**2)) - exp(-((x-3)**2 + (y-3)**2)) + 0.01*(x**2+y**2) - 0.5*exp(-((x-1.5)**2 + (y-2.5)**2)))

    def gradient(self, v):
        x = v[0]
        y = v[1]
        dfdx = 2*x*exp(-(x**2 + 0.2*y**2)) + (2*x - 6)*exp(-((x-3)**2 + (y-3)**2)) + 0.02*x + 0.5*(2*x-3)*exp(-((x-1.5)**2 + (y-2.5)**2))
        dfdy = 2*y*exp(-(x**2 + 0.2*y**2)) + (2*y - 6)*exp(-((x-3)**2 + (y-3)**2)) + 0.02*y + 0.3*(2*y-5)*exp(-((x-1.5)**2 + (y-2.5)**2))

        return array((dfdx,dfdy))

class QuarticPES(QCDriver):
    def __init__(self):
        QCDriver.__init__(self,2)

    def gradient(self, a):
        if len(a) != self.dimension:
            raise Exception("Wrong dimension")

        x = a[0]
        y = a[1]
        dzdx = 4*x**3 - 3*80*x**2 + 2*1616*x + 2*2*x*y**2 - 2*8*y*x - 80*y**2 
        dzdy = 2*2*x**2*y - 8*x**2 - 2*80*x*y + 2*1616*y + 4*y**3 - 3*8*y**2
        return array([dzdy, dzdx])

    def energy(self, a):
        if len(a) != self.dimension:
            raise Exception("Wrong dimension")

        x = a[0]
        y = a[1]
        z = (x**2 + y**2) * ((x - 40)**2 + (y - 4) ** 2)
        return (z)

class ReactionPathway:
    dimension = -1
    def __init__(self, reactants, products, f_test = lambda x: True, beadsCount = 10):
        assert type(reactants) == type(products) == ndarray

        if beadsCount <= 2:
            raise Exception("Must have beadsCount > 2 to form a meaningful path")

        self.reactants  = reactants
        self.products   = products
        self.beadsCount = beadsCount
        self.stateVec   = vectorInterpolate(reactants, products, beadsCount)
        
        assert len(reactants) == len(products)
        self.dimension = len(reactants) # dimension of PES
        
        # test to see if molecular geometry is bad or not
        pointsGood = map (f_test, self.stateVec.tolist())
        if not reduce(lambda a,b: a and b, pointsGood):
            raise Exception("Unhandled, some points were bad")

    def objFunc():
        pass

    def objFuncGrad():
        pass

    def dump(self):
        pass


def specialReduceXX(list, ks = [], f1 = lambda a,b: a-b, f2 = lambda a: a**2):
    """For a list of x_0, x_1, ... , x_(N-1)) and a list of scalars k_0, k_1, ..., 
    returns a list of length N-1 where each element of the output array is 
    f2(f1(k_i * x_i, k_i+1 * x_i+1)) ."""

    assert type(list) == ndarray
    assert len(list) >= 2
    assert len(ks) == 0 or len(ks) == len(list)
    
    # Fill with trivial value that won't change the result of computations
    if len(ks) == 0:
        ks = array(ones(len(list)))

    def specialReduce_(head, head1, tail, f1, f2, k, k1, ktail):
        reduction = f2 (f1 (k*head, k1*head1))
        if len(tail) == 0:
            return [reduction]
        else:
            return [reduction] + specialReduce_(head1, tail[0], tail[1:], f1, f2, k1, ktail[0], ktail[1:])

    return array(specialReduce_(list[0], list[1], list[2:], f1, f2, ks[0], ks[1], ks[2:]))

class NEB_l(ReactionPathway):
    def __init__(self, reactants, products, f_test, baseSprConst, qcDriver, beadsCount = 10, str_resolution = 500):
        ReactionPathway.__init__(self, reactants, products, f_test, beadsCount)
        self.baseSprConst = baseSprConst
        self.qcDriver = qcDriver
        self.tangents = zeros(beadsCount * self.dimension)
        self.tangents.shape = (beadsCount, self.dimension)

        # Make list of spring constants for every inter-bead separation
        # For the time being, these are uniform
        self.sprConstVec = array([self.baseSprConst for x in range(beadsCount - 1)])

class Func():
    def f():
        pass
    def fprime():
        pass

class LinFunc():
    def __init__(self, xs, ys):
        self.fs = scipy.interpolate.interp1d(xs, ys)
        self.grad = (ys[1] - ys[0]) / (xs[1] - xs[0])

    def f(self, x):
        return self.fs(x)[0]

    def fprime(self, x):
        return self.grad


class QuadFunc(Func):
    def __init__(self, coefficients):
        self.coefficients = coefficients

    def f(self, x):
        return dot(array((x**2, x, 1)), self.coefficients)

    def fprime(self, x):
        return 2 * self.coefficients[0] * x + self.coefficients[1]

class SplineFunc(Func):
    def __init__(self, xs, ys):
        self.spline_data = interpolate.splrep(xs, ys, s=0)
        
    def f(self, x):
        return interpolate.splev(x, self.spline_data, der=0)

    def fprime(self, x):
        return interpolate.splev(x, self.spline_data, der=1)


class PathRepresentation():
    def __init__(self, state_vec, beads_count, rho = lambda x: 1, str_resolution = 100):

        # vector of vectors defining the path
        self.state_vec = state_vec

        # number of vectors defining the path
        self.beads_count = beads_count
        self.dimensions = len(state_vec[0])

        self.str_resolution = str_resolution
        self.step = 1.0 / self.str_resolution

        self.fs = []
        self.path_tangents = []

        self.unit_interval = array((0.0,1.0))

        # TODO check all beads have same dimensionality

        self.max_integral_error = 1e-8

        self.rho = rho
        (int,err) = scipy.integrate.quad(rho, 0.0, 1.0)
        logger.info('Integral of spacing function was %lf', int)
        if abs(int - 1.0) > 0.001:
            raise Exception("bad spacing function")

        msg = "beads_count = %d\nstr_resolution = %d" % (beads_count, str_resolution)
        print msg

    def set_new_beads_count(self, x):
        self.beads_count = x

    def regen_path_func(self):
        """Rebuild a new path function and the derivative of the path based on the contents of state_vec."""
        assert len(self.state_vec) > 1

        for i in range(self.dimensions):

            ys = self.state_vec[:,i]

            # linear path
            if len(self.state_vec) == 2:
                self.fs.append(LinFunc(self.unit_interval, ys))

            # parabolic path
            elif len(self.state_vec) == 3:

                # TODO: at present, transition state assumed to be half way ebtween reacts and prods
                ps = array((0.0, 0.5, 1.0))
                ps_x_pow_2 = ps**2
                ps_x_pow_1 = ps
                ps_x_pow_0 = ones(len(ps_x_pow_1))

                A = column_stack((ps_x_pow_2, ps_x_pow_1, ps_x_pow_0))

                quadratic_coeffs = linalg.solve(A,ys)

                self.fs.append(QuadFunc(quadratic_coeffs))

            else:
                # spline path
                points_cnt = len(self.state_vec)
                xs = arange(0.0, 1.0 + 1.0 / (points_cnt - 1), 1.0 / (points_cnt - 1))
                print "points_cnt =", points_cnt
                print "xs =", xs
                self.fs.append(SplineFunc(xs,ys))

        tmp_fx = self.fs[0].f
        tmp_fy = self.fs[1].f
        print "fs =", self.fs
        print "the thing = ", tmp_fx(0.5), tmp_fy(0.5)

    def get_total_str_len(self):
        """Returns the a duple of the total length of the string and a list of 
        pairs (x,y), where x a distance along the normalised path (i.e. on 
        [0,1]) and y is the corresponding distance along the string (i.e. on
        [0,string_len])."""
        
        # function, integral of which gives total path length
        def arc_dist_func(x):
            output = 0
            for a in self.fs:
                output += a.fprime(x)**2
            return sqrt(output)

        # number of points to chop the string into
        param_steps = arange(0, 1, self.step)

        list = []
        cumm_dist = 0
        for i in range(self.str_resolution):
            lower, upper = i * self.step, (i + 1) * self.step
            (integral, error) = scipy.integrate.quad(arc_dist_func, lower, upper)
            cumm_dist += integral

            assert error < self.max_integral_error

            list.append(cumm_dist)

        return (list[-1], zip(param_steps, list))

    def generate_beads(self, update = False):
        """Returns an array of the vectors of the coordinates of beads along a reaction path,
        according to the established path (line, parabola or spline) and the parameterisation
        density"""

        assert len(self.fs) > 1

        (total_str_len, incremental_positions) = self.get_total_str_len()

        normd_positions = self.generate_normd_positions(total_str_len, incremental_positions)

        bead_vectors = []
        bead_tangents = []
        print "normd_positions =", normd_positions
        for str_pos in normd_positions:
            bead_vectors.append(self.get_bead_coords(str_pos))
            bead_tangents.append(self.get_tangent(str_pos))

        print "bead_vectors =", bead_vectors

        if update:
            self.state_vec = bead_vectors
            self.path_tangents = bead_tangents

        return bead_vectors
        
    def get_str_positions(self):
        """Based on the provided density function self.rho(x) and 
        self.bead_count, generates the fractional positions along the string 
        at which beads should occur."""

        param_steps = arange(0, 1 - self.step, self.step)
        integrated_density_inc = 1.0 / (self.beads_count - 1.0)
        requirement_for_next_bead = integrated_density_inc

        integral = 0
        str_positions = []
        for s in param_steps:
            (i, err) = scipy.integrate.quad(self.rho, s, s + self.step)
            integral += i
            if integral > requirement_for_next_bead:
                """msg = "rfnb = %f integral =  %f" % (requirement_for_next_bead, integral)
                print msg"""
                str_positions.append(s)
                requirement_for_next_bead += integrated_density_inc
        
        print "str_positions =", str_positions
        return str_positions

    def get_bead_coords(self, x):
        """Returns the coordinates of the bead at point x <- [0,1]."""
        bead_coords = []
        for f in self.fs:
            bead_coords.append(f.f(x))

        return (array(bead_coords).flatten())

    def get_tangent(self, x):
        """Returns the tangent to the path at point x <- [0,1]."""

        path_tangent = []
        for f in self.fs:
            path_tangent.append(f.fprime(x))

        t = array(path_tangent).flatten()
        t = t / linalg.norm(t)
        return t

    def generate_normd_positions(self, total_str_len, incremental_positions):
        """Returns a list of distances along the string in terms of the normalised 
        coordinate, based on desired fractional distances along string."""

        fractional_positions = self.get_str_positions()

        normd_positions = []

        print "fractional_positions: ", fractional_positions, "\n"
        for frac_pos in fractional_positions:
            print "frac_pos = ", frac_pos, "total_str_len = ", total_str_len
            for (norm, str) in incremental_positions:

                if str >= frac_pos * total_str_len:
                    print "norm = ", norm
                    normd_positions.append(norm)
                    break

        print "normed_positions =", normd_positions
        return normd_positions


class GrowingString(ReactionPathway):
    def __init__(self, reactants, products, f_test, f_density, qcDriver, beads_count = 10):
        ReactionPathway.__init__(self, reactants, products, f_test, beads_count)
        self.baseSprConst = baseSprConst
        self.qcDriver = qcDriver

        self.path_rep = PathRepresentation([reactants, products], beads_count)

    def step_opt():
        pass

def project_out(component_to_remove, vector):
    """Projects the component of 'vector' that list along 'component_to_remove'
    out of 'vector' and returns it."""
    projection = dot(component_to_remove, vector)
    output = vector - component_to_remove * vector
    return output

class NEB(ReactionPathway):
"""Implements a Nudged Elastic Band (NEB) transition state searcher."""

    def __init__(self, reactants, products, f_test, baseSprConst, qcDriver, beadsCount = 10):
        ReactionPathway.__init__(self, reactants, products, f_test, beadsCount)
        self.baseSprConst = baseSprConst
        self.qcDriver = qcDriver
        self.tangents = zeros(beadsCount * self.dimension)
        self.tangents.shape = (beadsCount, self.dimension)

        # Make list of spring constants for every inter-bead separation
        # For the time being, these are uniform
        self.sprConstVec = array([self.baseSprConst for x in range(beadsCount - 1)])

    def specialReduce(self, list, ks = [], f1 = lambda a,b: a-b, f2 = lambda a: a**2):
        """For a list of x_0, x_1, ... , x_(N-1)) and a list of scalars k_0, k_1, ..., 
        returns a list of length N-1 where each element of the output array is 
        f2(f1(k_i * x_i, k_i+1 * x_i+1)) ."""

        assert type(list) == ndarray
        assert len(list) >= 2
        assert len(ks) == 0 or len(ks) == len(list)
        
        # Fill with trivial value that won't change the result of computations
        if len(ks) == 0:
            ks = array(ones(len(list)))

        assert type(ks) == ndarray
        for a in range(len(ks)):
            list[a] = list[a] * ks[a]

        print "list =",list
        currDim = list.shape[1]  # generate zero vector of the same dimension of the list of input dimensions
        print "cd = ", currDim
        z = array(zeros(currDim))
        listPos = vstack((list, z))
        listNeg = vstack((z, list))

        list = f1 (listPos, listNeg)
        list = f2 (list[1:-1])

        return list

    def updateTangents(self):
        # terminal beads have no tangent
        self.tangents[0]  = zeros(self.dimension)
        self.tangents[-1] = zeros(self.dimension)
        for i in range(self.beadsCount)[1:-1]:
            self.tangents[i] = ( (self.stateVec[i] - self.stateVec[i-1]) + (self.stateVec[i+1] - self.stateVec[i]) ) / 2
            self.tangents[i] /= linalg.norm(self.tangents[i], 2)

    def updateBeadSeparations(self):
        self.beadSeparationSqrsSums = array( map (sum, self.specialReduce(self.stateVec).tolist()) )
        self.beadSeparationSqrsSums.shape = (self.beadsCount - 1, 1)

    def getStateAsArray(self):
        return self.stateVec.flatten()

    def objFunc(self, newStateVec = []):
        assert size(self.stateVec) == self.beadsCount * self.dimension

        if newStateVec != []:
            self.stateVec = array(newStateVec)
            self.stateVec.shape = (self.beadsCount, self.dimension)

        self.updateTangents()
        self.updateBeadSeparations()
        
        forceConstsBySeparationsSquared = multiply(self.sprConstVec, self.beadSeparationSqrsSums.flatten()).transpose()
        springEnergies = 0.5 * ndarray.sum (forceConstsBySeparationsSquared)

        # The following code block will need to be replaced for parallel operation
        pesEnergies = 0
        for beadVec in self.stateVec[1:-1]:
            pesEnergies += self.qcDriver.energy(beadVec)

        return (pesEnergies + springEnergies)

    def objFuncGrad(self, newStateVec = []):

        # If a state vector has been specified, return the value of the 
        # objective function for this new state and set the state of self
        # to the new state.
        if newStateVec != []:
            self.stateVec = array(newStateVec)
            self.stateVec.shape = (self.beadsCount, self.dimension)

        self.updateBeadSeparations()
        self.updateTangents()

        separationsVec = self.beadSeparationSqrsSums ** 0.5
        separationsDiffs = self.specialReduce(separationsVec, self.sprConstVec, f2 = lambda x: x)
        assert len(separationsDiffs) == self.beadsCount - 2

#        print "sd =", separationsDiffs.flatten(), "t =", self.tangents[1:-1]
        springForces = multiply(separationsDiffs.flatten(), self.tangents[1:-1].transpose()).transpose()
        springForces = vstack((zeros(self.dimension), springForces, zeros(self.dimension)))
        print "sf =", springForces

        pesForces = array(zeros(self.beadsCount * self.dimension))
        pesForces.shape = (self.beadsCount, self.dimension)
#        print "pesf =", pesForces

        for i in range(self.beadsCount)[1:-1]:
            pesForces[i] = -self.qcDriver.gradient(self.stateVec[i])
#            print "pesbefore =", pesForces[i]
            # OLD LINE:
#            pesForces[i] = pesForces[i] - dot(pesForces[i], self.tangents[i]) * self.tangents[i]

            # NEW LINE:
            pesForces[i] = project_out(self.tangents[i], pesForces[i])

#            print "pesafter =", pesForces[i], "t =", self.tangents[i]

        gradientsVec = -1 * (pesForces + springForces)

        return gradientsVec.flatten()


def vectorInterpolate(start, end, beadsCount):
    """start: start vector
    end: end vector
    points: TOTAL number of points in path, INCLUDING start and final point"""

    assert len(start) == len(end)
    assert type(end) == ndarray
    assert type(start) == ndarray
    assert beadsCount > 2

    start = array(start, dtype=float64)
    end = array(end, dtype=float64)

    inc = (end - start) / (beadsCount - 1)
    output = [ start + x * inc for x in range(beadsCount) ]

    return array(output)


reactants = array([0,0])
products = array([3,3])
if len(reactants) != len(products):
    print "Reactants/Products must be the same size"

print "Reactants vector size =", len(reactants), "Products vector size =", len(products)

def test_path_rep():
    ts = array((2.5, 1.9))
    ts2 = array((1.9, 2.5))
    r = array((reactants, ts, ts2, products))
    x = PathRepresentation(r, 5)

    str_len = x.get_total_str_len()
    print "str_len =", str_len

    # Build linear, quadratic or spline representation of the path,
    # depending on the number of points.
    x.regen_path_func()
    x.set_new_beads_count(10)
    x.generate_beads(update=True)
    print "tangents =", x.path_tangents

    plot2D(x)


def plot2D(react_path, path_res = 0.05):
    """Given a path object react_path, displays the a 2D depiction of it's 
    first two dimensions as a graph."""
    g = Gnuplot.Gnuplot(debug=1)

    g.xlabel('x')
    g.ylabel('y')

    # Get some tmp filenames
    (fd, tmp_file1,) = tempfile.mkstemp(text=1)
    (fd, tmp_file2,) = tempfile.mkstemp(text=1)
    (fd, tmp_file3,) = tempfile.mkstemp(text=1)

    params = arange(0, 1 + path_res, path_res)
    f_x = react_path.fs[0].f
    f_y = react_path.fs[1].f
    xs = array ([f_x(p) for p in params])
    ys = array ([f_y(p) for p in params])
    print "params: ", params
    print "xs: ", xs
    print "ys: ", ys

    # smooth path
    smooth_path = vstack((xs,ys)).transpose()
    print "smooth_path =", smooth_path
    Gnuplot.Data(smooth_path, filename=tmp_file1, inline=0, binary=0)
    
    # state vector
    data1 = react_path.state_vec
    Gnuplot.Data(data1, filename=tmp_file2, inline=0, binary=0)

    # points along path
    beads = react_path.generate_beads()
    Gnuplot.Data(beads, filename=tmp_file3, inline=0, binary=0)

    # draw tangent to the path
    pt_ix = 4
    t0_grad = react_path.path_tangents[pt_ix][1] / react_path.path_tangents[pt_ix][0]
    t0_str = "%f * (x - %f) + %f" % (t0_grad, react_path.state_vec[pt_ix][0], react_path.state_vec[pt_ix][1])
    t0_func = Gnuplot.Func(t0_str)

    # PLOT THE VARIOUS PATHS
    g.plot(t0_func, Gnuplot.File(tmp_file1, binary=0, title="Smooth", with_ = "linespoints"), Gnuplot.File(tmp_file2, binary=0, with_ = "linespoints"), Gnuplot.File(tmp_file3, binary=0, title="from class", with_ = "linespoints"))
    raw_input('Press to continue...\n')

    os.unlink(tmp_file1)
    os.unlink(tmp_file2)
    os.unlink(tmp_file3)

def mytest_NEB():
    from scipy.optimize import fmin_bfgs

    defaultSprConst = 0.01
    neb = NEB(reactants, products, lambda x: True, defaultSprConst, GaussianPES(), beadsCount = 15)
    initState = neb.getStateAsArray()
    opt = fmin_bfgs(neb.objFunc, initState, fprime=neb.objFuncGrad)
    gr = neb.objFuncGrad(opt)
    n = linalg.norm(gr)
    i = 0
    while n > 0.001 and i < 4:
        print "n =",n
        opt = fmin_bfgs(neb.objFunc, opt, fprime=neb.objFuncGrad)
        gr = neb.objFuncGrad(opt)
        n = linalg.norm(gr)
        i += 1


    # Points on grid to draw PES
    ps = 20.0
    xrange = arange(ps)*(5.0/ps) - 1
    yrange = arange(ps)*(5.0/ps) - 1

    # Make a 2-d array containing a function of x and y.  First create
    # xm and ym which contain the x and y values in a matrix form that
    # can be `broadcast' into a matrix of the appropriate shape:
    gpes = GaussianPES2()
    g = Gnuplot.Gnuplot(debug=1)
    g('set data style lines')
    g('set hidden')
    g.xlabel('x')
    g.ylabel('y')

    # Get some tmp filenames
    (fd, tmpPESDataFile,) = tempfile.mkstemp(text=1)
    (fd, tmpPathDataFile,) = tempfile.mkstemp(text=1)
    Gnuplot.funcutils.compute_GridData(xrange, yrange, lambda x,y: gpes.energy([x,y]),filename=tmpPESDataFile, binary=0)
    opt.shape = (-1,2)
    print "opt = ", opt
    pathEnergies = array (map (gpes.energy, opt.tolist()))
    print "pathEnergies = ", pathEnergies
    pathEnergies += 0.02
    xs = array(opt[:,0])
    ys = array(opt[:,1])
    print "xs =",xs, "ys =",ys
    data = transpose((xs, ys, pathEnergies))
    Gnuplot.Data(data, filename=tmpPathDataFile, inline=0, binary=0)

    # PLOT SURFACE AND PATH
    g.splot(Gnuplot.File(tmpPESDataFile, binary=0), Gnuplot.File(tmpPathDataFile, binary=0, with_="linespoints"))
    raw_input('Press to continue...\n')

    os.unlink(tmpPESDataFile)
    os.unlink(tmpPathDataFile)

    return opt

# parabolas
# (x**2 + y**2)*((x-40)**2 + (y-4)**2)

# gaussians
# f(x,y) = -exp(-(x**2 + y**2)) - exp(-((x-3)**2 + (y-3)**2))
# df/dx = 2*x*exp(-(x**2 + y**2)) + (2*x - 6)*exp(-((x-3)**2 + (y-3)**2))
# df/dy = 2*y*exp(-(x**2 + y**2)) + (2*y - 6)*exp(-((x-3)**2 + (y-3)**2))

def e_test(v):
    x = v[0]
    y = v[1]
    return (-exp(-(x**2 + y**2)) - exp(-((x-3)**2 + (y-3)**2)) + 0.01*(x**2+y**2))

def g_test(v):
    x = v[0]
    y = v[1]
    dfdx = 2*x*exp(-(x**2 + y**2)) + (2*x - 6)*exp(-((x-3)**2 + (y-3)**2)) + 0.02*x
    dfdy = 2*y*exp(-(x**2 + y**2)) + (2*y - 6)*exp(-((x-3)**2 + (y-3)**2)) + 0.02*y
    return array((dfdx,dfdy))

def rosen_der(x):
    xm = x[1:-1]
    xm_m1 = x[:-2]
    xm_p1 = x[2:]
    der = zeros_like(x)
    der[1:-1] = 200*(xm-xm_m1**2) - 400*(xm_p1 - xm**2)*xm - 2*(1-xm)
    der[0] = -400*x[0]*(x[1]-x[0]**2) - 2*(1-x[0])
    der[-1] = 200*(x[-1]-x[-2]**2)
    return der

def rosen(x):
    """The Rosenbrock function"""
    return sum(100.0*(x[1:]-x[:-1]**2.0)**2.0 + (1-x[:-1])**2.0)


