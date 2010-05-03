import pickle
import os

from aof.path import Path
import numpy as np
from aof.common import vector_angle
import aof.func as func
import scipy as sp
from aof.threepointmin import ts_3p_gr

class PathTools:
    """
    Implements operations on reaction pathways, such as estimation of 
    transition states using gradient/energy information.

    >>> pt = PathTools([0,1,2,3], [1,2,3,2])
    >>> pt.steps
    array([ 0.,  1.,  2.,  3.])

    >>> pt.ts_highest()
    [(3, array([2]), 2.0, 2.0, 2.0, 2, 2)]

    >>> pt = PathTools([0,1,2,3], [1,2,3,2], [0,1,-0.1,0])
    >>> res1 = pt.ts_splcub()

    >>> pt = PathTools([[0,0],[1,0],[2,0],[3.,0]], [1,2,3,2.], [[0,0],[1,0],[-0.1,0],[0,0]])
    >>> res2 = pt.ts_splcub()
    >>> res1[0][0] == res2[0][0]
    True

    >>> np.round(res1[0][0], 0)
    3.0
    >>> res1[0][0] > 3
    True

    Tests on path generated from a parabola.

    >>> xs = (np.arange(10) - 5) / 2.0
    >>> f = lambda x: -x*x
    >>> g = lambda x: -2*x
    >>> ys = f(xs)
    >>> gs = g(xs)
    >>> pt = PathTools(xs, ys, gs)
    >>> energy, pos, _, _, _, _, _ = pt.ts_splcub()[0]
    >>> np.round(energy) == 0
    True
    >>> (np.round(pos) == 0).all()
    True
    >>> type(str(pt))
    <type 'str'>


    Tests on path generated from a parabola, again, but shifted.

    >>> xs = (np.arange(10) - 5.2) / 2.0
    >>> f = lambda x: -x*x
    >>> g = lambda x: -2*x
    >>> ys = f(xs)
    >>> gs = g(xs)
    >>> pt = PathTools(xs, ys, gs)
    >>> energy, pos, _, _, _, _, _ = pt.ts_splcub()[0]
    >>> np.round(energy) == 0
    True
    >>> (np.round(pos) == 0).all()
    True

    >>> pt = PathTools([0,1,2,3,4], [1,2,3,2,1])
    >>> e, p, s0, s1, s_ts, i_, i = pt.ts_spl()[0]
    >>> np.round([e,p])
    array([ 3.,  2.])

    >>> pt = PathTools([0,1,2,3,4], [1,2,3,2,1], [0,1,-0.1,0,1])
    >>> pt.ts_spl()[0] == (e, p, s0, s1, s_ts, i_, i)
    True

    >>> pt = PathTools([0,1,2,3,4], [1,2,3,2,1])
    >>> e = pt.ts_bell()[0]
    >>> np.round(np.array(e), 2)
    array([ 3.,  2.,  1.,  2.,  1.,  2.])

    >>> pt = PathTools([0,1,2,3,4,5], [1,3,5,5,3,1])
    >>> e = pt.ts_bell()[0]
    >>> np.round(np.array(e), 2)
    array([ 5.3,  2.5,  2. ,  3. ,  2. ,  3. ])

    >>> pt = PathTools([0,1,2,5,6], [1,3,5,3,1])
    >>> e = pt.ts_bell()[0]
    >>> np.round(np.array(e), 2)
    array([ 5.54,  2.83,  2.  ,  5.  ,  2.  ,  3.  ])


    """
    def __init__(self, state, energies, gradients=None, startsteps = None):

        # string for __str__ to print
        self.s = []

        self.n = len(energies)
        self.s.append("Beads: %d" % self.n)
        self.state = np.array(state).reshape(self.n, -1)
        self.energies = np.array(energies)

        if gradients != None:
            self.gradients = np.array(gradients).reshape(self.n, -1)
            assert self.state.shape == self.gradients.shape

        assert len(state) == len(energies)

        if startsteps == None:
            self.steps = np.zeros(self.n)

            x = self.state[1]
            x_ = self.state[0]
            for i in range(self.n)[1:]:
                x = self.state[i]
                x_ = self.state[i-1]
                self.steps[i] = np.linalg.norm(x -x_) + self.steps[i-1]

        else:
            assert len(startsteps) == self.n
            self.steps = startsteps

        # set up array of tangents, not based on a spline representation of the path
        self.non_spl_grads = []
        x = self.state[1]
        x_ = self.state[0]
        l = np.linalg.norm(x - x_)
        self.non_spl_grads.append((x - x_) / l)
        for i in range(self.n)[1:]:
            x = self.state[i]
            x_ = self.state[i-1]
            l = np.linalg.norm(x - x_)
            self.non_spl_grads.append((x - x_) / l)

        self.non_spl_grads = np.array(self.non_spl_grads)
        assert len(self.non_spl_grads) == self.n, "%d != %d" % (len(self.non_spl_grads), self.n)


        # build fresh functional representation of optimisation 
        # coordinates as a function of a path parameter s
        self.xs = Path(self.state, self.steps)

        # Check to see whether spline path is comparable to Pythagorean one.
        # TODO: ideally, self.steps should be updated so that it's self 
        # consistent with the steps generated by the Path object, but at 
        # present, calculation of string length is too slow, so it's only done 
        # once and a simple comaprison is made.
        diff = lambda a,b:np.abs(a-b)
        self.arc = func.Integral(self.xs.tangent_length)
        l = np.array([self.arc(x) for x in self.xs.xs])
        self.s.append("Path length: %s" % l[-1])
        err = l - self.steps
        err = [diff(err[i], err[i-1]) for i in range(len(err))[1:]]
        self.s.append("Difference between Pythag v.s. spline positions: %s" % np.array(err).round(4))

        # There have been some problems with the calculation of the slope along the path
        # This calculates it via an alternate method
        self.para_forces_fd = []
        self.use_energy_based_dEds_calc = False
        if self.use_energy_based_dEds_calc:
            ss = self.steps
            Es = self.energies
            self.dEds_all = np.zeros(self.n)
            for i in range(self.n):
                if i == 0:
                    tmp = (Es[i+1] - Es[i]) / np.linalg.norm(ss[i+1] - ss[i])
                elif i == self.n - 1:
                    tmp = (Es[i] - Es[i-1]) / np.linalg.norm(ss[i] - ss[i-1])
                else:
                    tmp = (Es[i+1] - Es[i-1]) / np.linalg.norm(ss[i+1] - ss[i-1])
                self.para_forces_fd.append(tmp)
                self.dEds_all[i] = tmp

    def __str__(self):
        return '\n'.join(self.s)

    def modeandcurvature(self, s0, leftbd, rightbd, cs_forcart):
        """The mode along the path in the point s0 and
        the curvature for it are given back in several
        possible approximations
        """
        if leftbd == rightbd:
            leftbd -= 1
            rightbd += 1
        self.cs = cs_forcart.copy()
        self.cs.set_internals(self.state[leftbd])
        leftcoord = self.cs.get_cartesians()
        self.cs.set_internals(self.state[rightbd])
        rightcoord = self.cs.get_cartesians()

        modedirect = rightcoord - leftcoord
        normer = np.sqrt(sum(sum(modedirect * modedirect)))
        modedirect /= normer

        modeint = self.state[rightbd] - self.state[leftbd]
        normer = np.sqrt(sum(modeint * modeint))
        modeint /= normer
        transfer, error = self.cs.get_transform_matrix(self.xs(s0))
        modefromint = np.dot( np.asarray(modeint), transfer)

        modeint = self.state[-1] - self.state[0]
        normer = np.sqrt(sum(modeint * modeint))
        modeint /= normer
        transfer, error = self.cs.get_transform_matrix(self.xs(s0))
        modeallpath = np.dot( np.asarray(modeint), transfer)

        modeint = self.xs.fprime(s0)
        normer = np.sqrt(sum(modeint * modeint))
        modeint /= normer
        modepath = np.dot(np.asarray(modeint), transfer)

        modefromint = np.reshape(modefromint, np.shape(modedirect))
        modepath = np.reshape(modepath, np.shape(modedirect))
        modeallpath = np.reshape(modeallpath, np.shape(modedirect))

        return ("first to last bead", modeallpath),  ("directinternal", modefromint), ("frompath", modepath)


    def ts_spl(self, tol=1e-10):
        """Returns list of all transition state(s) that appear to exist along
        the reaction pathway."""

        n = self.n
        Es = self.energies.reshape(-1,1)
        ss = self.steps.copy()

        ys = self.state.copy()

        E = Path(Es, ss)

        ts_list = []
        for i in range(n)[1:]:
            s0 = ss[i-1]
            s1 = ss[i]
            dEds_0 = E.fprime(s0)
            dEds_1 = E.fprime(s1)
#            print "dEds_0, dEds_1 %f, %f" % (dEds_0, dEds_1)

            if dEds_0 > 0 and dEds_1 < 0:
                #print "ts_spl: TS in %f %f" % (s0,s1)
                f = lambda x: np.atleast_1d(E.fprime(x)**2)[0]
                assert s0 < s1, "%f %f" % (s0, s1)
                s_ts, fval, ierr, numfunc = sp.optimize.fminbound(f, s0, s1, full_output=1)

                # FIXME: a bit dodgy
                assert fval < 0.001
                ts_e = E(s_ts)
                assert ts_e.size == 1
                ts_e = ts_e[0]
                ts = self.xs(s_ts)
                ts_list.append((ts_e, ts, s0, s1, s_ts, i-1, i))

        ts_list.sort()
        return ts_list

    def ts_splavg(self, tol=1e-10):
        """
        Uses a spline representation of the molecular coordinates and 
        a cubic polynomial defined from the slope / value of the energy 
        for pairs of points along the path.
        """

        ys = self.state.copy()
        ss = self.steps
        Es = self.energies
        self.s.append("Begin ts_splavg()")
        self.s.append("Es: %s" % Es)

        self.plot_str = ""
        for s, e in zip(ss, Es):
            self.plot_str += "%f\t%f\n" % (s, e)

       
        ts_list = []

        for i in range(self.n)[1:]:#-1]:
            # For each pair of points along the path, find the minimum
            # energy and check that the gradient is also zero.
            E_0 = Es[i-1]
            E_1 = Es[i]

            s0 = ss[i-1]
            s1 = ss[i]
            
            dEdx_0 = self.gradients[i-1]
            dEdx_1 = self.gradients[i]
            dxds_0 = self.xs.fprime(ss[i-1])
            dxds_1 = self.xs.fprime(ss[i])

            #energy gradient at "left/right" bead along path
            dEds_0 = np.dot(dEdx_0, dxds_0)
            dEds_1 = np.dot(dEdx_1, dxds_1)

            if self.use_energy_based_dEds_calc:
                dEds_0 = self.dEds_all[i-1]
                dEds_1 = self.dEds_all[i]

            dEdss = np.array([dEds_0, dEds_1])

            self.s.append("E_1 %s" % E_1)
            if (E_1 >= E_0 and dEds_1 <= 0) or (E_1 <= E_0 and dEds_0 > 0):
                #print "ts_splcub_avg: TS in %f %f" % (ss[i-1],ss[i])

                E_ts = (E_1 + E_0) / 2
                s_ts = (s1 + s0) / 2
                ts_list.append((E_ts, self.xs(s_ts), s0, s1, s_ts, i-1, i))

        ts_list.sort()
        return ts_list


    def ts_bell(self):
        ys = self.state.copy()

        ss = self.steps
        Es = self.energies
        E = Path(Es, ss)

        samples = np.arange(0, 1, 0.001) * ss[-1]
        E_points = np.array([E(p) for p in samples])
        assert (np.array([E(p) for p in ss]) - Es).round().sum() == 0, "%s\n%s" % ([E(p) for p in ss], Es)

        sTS = samples[E_points.argmax()]
        yTS = self.xs(sTS)

        l = []
        for i in range(len(ss))[1:]:
            if ss[i-1] < sTS <= ss[i]:
                sL = ss[i-1]
                sR = ss[i]
                yR = ys[i]
                yL = ys[i-1]
                if sTS - sL < sR - sTS:
                    yTS = yL + (sTS - sL) / (sR - sL) * (yR - yL)
                else:
                    yTS = yR + (sTS - sR) / (sR - sL) * (yR - yL)
                l.append((E_points.max(), yTS, sL, sR, sTS, i-1, i))
                break

        return l


    def ts_splcub(self, tol=1e-10):
        """
        Uses a spline representation of the molecular coordinates and 
        a cubic polynomial defined from the slope / value of the energy 
        for pairs of points along the path.
        """

        ys = self.state.copy()

        ss = self.steps
        Es = self.energies
        self.s.append("Begin ts_splcub()")

        self.s.append("Es: %s" % Es)

        self.plot_str = ""
        for s, e in zip(ss, Es):
            self.plot_str += "%f\t%f\n" % (s, e)

        # build fresh functional representation of optimisation 
        # coordinates as a function of a path parameter s

        
        ts_list = []

        self.para_forces = []

              
        for i in range(self.n)[1:]:#-1]:
            # For each pair of points along the path, find the minimum
            # energy and check that the gradient is also zero.
            E_0 = Es[i-1]
            E_1 = Es[i]
            dEdx_0 = self.gradients[i-1]
            dEdx_1 = self.gradients[i]
            dxds_0 = self.xs.fprime(ss[i-1])
            dxds_1 = self.xs.fprime(ss[i])

            # energy gradient at "left/right" bead along path
            dEds_0 = np.dot(dEdx_0, dxds_0)
            dEds_1 = np.dot(dEdx_1, dxds_1)
            
            # debugging
            dEds_0_ = np.dot(dEdx_0, self.non_spl_grads[i-1])
            dEds_1_ = np.dot(dEdx_1, self.non_spl_grads[i])

            self.para_forces.append(dEds_1)

            if self.use_energy_based_dEds_calc:
                dEds_0 = self.dEds_all[i-1]
                dEds_1 = self.dEds_all[i]
            dEdss = np.array([dEds_0, dEds_1])

            self.s.append("E_1 %s" % E_1)
            self.s.append("Checking: i = %d E_1 = %f E_0 = %f dEds_1 = %f dEds_0 = %f" % (i, E_1, E_0, dEds_1, dEds_0))
            self.s.append("Non-spline dEds_1 = %f dEds_0 = %f" % (dEds_1_, dEds_0_))

            if (E_1 >= E_0 and dEds_1 <= 0) or (E_1 <= E_0 and dEds_0 > 0):
                #print "ts_splcub: TS in %f %f" % (ss[i-1],ss[i])
                self.s.append("Found")

                cub = func.CubicFunc(ss[i-1:i+1], Es[i-1:i+1], dEdss)
#                print ss[i-2:i+1], Es[i-2:i+1]
#                print ss, Es
#                print i
#                if i < 2:
#                    continue
#                cub = func.QuadFunc(ss[i-2:i+1], Es[i-2:i+1])
#                print ss[i], cub(ss[i]), Es[i]
                self.s.append("ss[i-1:i+1]: %s" % ss[i-1:i+1])

                self.s.append("cub: %s" % cub)

                # find the stationary points of the cubic
                statpts = cub.stat_points()
                self.s.append("statpts: %s" % statpts)
                assert statpts != []
                found = 0
                for p in statpts:
                    # test curvature
                    if cub.fprimeprime(p) < 0:
                        ts_list.append((cub(p), self.xs(p), ss[i-1], ss[i], p, i-1, i))
                        found += 1

#                assert found == 1, "Must be exactly 1 stationary points in cubic path segment but there were %d" % found

                self.plot_str += "\n\n%f\t%f\n" % (p, cub(p))

        ts_list.sort()
        return ts_list

    def ts_highest(self):
        """
        Just picks the highest energy from along the path.
        """
        i = self.energies.argmax()
        ts_list = [(self.energies[i], self.state[i], self.steps[i], self.steps[i], self.steps[i], i, i)]

        return ts_list

    def ts_threepoints(self, withmove = False):
        """Uses the threepointmin module to get an approximation just
        from the three points supposed to be next nearest to the transition state

        if withmove = True, calculates also the approximation with the beads
        one to the left and ones to the right of the hightest bead
        """

        i = self.energies.argmax()
        ts_list = []
        if withmove:
             xts, gts, ets, gpr1, gpr2, work =  ts_3p_gr(self.state[i-2], self.state[i-1], self.state[i], self.gradients[i-2], self.gradients[i-1], self.gradients[i], self.energies[i-2], self.energies[i-1], self.energies[i])
             ts_list.append((ets, xts, self.steps[i-1], self.steps[i+1],self.steps[i], i-1, i+1))
             xts, gts, ets, gpr1, gpr2, work =  ts_3p_gr(self.state[i], self.state[i+1], self.state[i+2], self.gradients[i], self.gradients[i+1], self.gradients[i+2], self.energies[i], self.energies[i+1], self.energies[i+2])
             ts_list.append((ets, xts, self.steps[i-1], self.steps[i+1],self.steps[i], i-1, i+1))

        xts, gts, ets, gpr1, gpr2, work =  ts_3p_gr(self.state[i-1], self.state[i], self.state[i+1], self.gradients[i-1], self.gradients[i], self.gradients[i+1], self.energies[i-1], self.energies[i], self.energies[i+1])
        if not work:
            print "WARNING: this transition state approximation is rather far away from the initial path"
            print "Please verify that it makes sense before using it"
        ts_list.append((ets, xts, self.steps[i-1], self.steps[i+1],self.steps[i], i-1, i+1))

        return ts_list


def pickle_path(mi, CoS, file):
    a,b,c,d,e = CoS.path_tuple()
    print "PICKLE",d, e
    cs = mi.build_coord_sys(a[0])
    f = open(file, 'wb')
    pickle.dump((a,b,c,d,e,cs), f)
    f.close()

plot_s = \
"""
plot "%(fn)s", "%(fn)s" smooth cspline
"""
def gnuplot_path(state, es, filename):
    assert len(state) == len(es)

    N = len(es)
    p = Path(state, np.arange(N))

    arc = func.Integral(p.tangent_length)
    l = np.array([arc(x) for x in np.arange(N)])
    print "l", l

    s = '0\t%f\n' % es[0]
    bead_pos = 0
    for i in range(N)[1:]:
        v = state[i] - state[0]
        bead_pos += np.sqrt(np.dot(v,v))
        s += '%f\t%f\n' % (l[i], es[i])

    f = open(filename + '.data', 'w')
    f.write(s)
    f.close()

    f = open(filename + '.gp', 'w')
    d = {'fn': filename + '.data'}
    f.write(plot_s % d)
    f.close()
    os.system('gnuplot -persist ' + filename + '.gp')

        
    

# Testing the examples in __doc__strings, execute
# "python gxmatrix.py", eventualy with "-v" option appended:
if __name__ == "__main__":
    import doctest
    doctest.testmod()

# You need to add "set modeline" and eventually "set modelines=5"
# to your ~/.vimrc for this to take effect.
# Dont (accidentally) delete these lines! Unless you do it intentionally ...
# Default options for vim:sw=4:expandtab:smarttab:autoindent:syntax


