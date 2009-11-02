import sys
import unittest
import os
import pickle

import numpy
import ase

import aof
import aof.coord_sys as cs
import aof.common as common
from aof.common import file2str

print "__file__", __file__

def geom_str_summ(s,n=2):
    """Summarises a string containing a molecular geometry so that very similar 
    geometries can be compared. For testing purposes."""

    import re
    numbers = re.findall(r"\d+\.\d*", s.lower())
    numbers = [str(round(float(i),n)) for i in numbers]

    symbols = re.findall(r"[a-z]+", s.lower())
    
    summary = symbols + numbers
    summary = ''.join(summary)

    return summary


class TestZMatrixAndAtom(aof.test.MyTestCase):

    def setUp(self):
        self.original_dir = os.getcwd()
        new_dir = os.path.dirname(__file__)
        if new_dir != '':
            os.chdir()

    
    def tearDown(self):
        os.chdir(self.original_dir)

    def test_ZMatrix(self):
      
        hexane_zmt = file2str("hexane.zmt")

        z = cs.ZMatrix(hexane_zmt)
        print "Testing hexane.zmt -> xyz"
        self.assertEqual(geom_str_summ(z.xyz_str()), geom_str_summ(file2str("hexane.xyz")))

        print "Testing hexane2.zmt -> zmt"
        self.assertEqual(geom_str_summ(z.zmt_str()), geom_str_summ(file2str("hexane2.zmt")))

        z = cs.ZMatrix(file2str("benzyl.zmt"))
        print "Testing benzyl.zmt -> xyz"
        self.assertEqual(geom_str_summ(file2str("benzyl.xyz")), geom_str_summ(z.xyz_str()))

    def test_ZMatrix_BigComplex(self):
        print "Test Sum of all Cartesian Coordinates"
        z = cs.ZMatrix(file2str("bigComplex.zmt"))
        xyz_str = z.xyz_str()

        import re
        list = re.findall(r"[+-]?\d+\.\d*", xyz_str)
        var_sum = sum([float(n) for n in list])

        self.assertAlmostEqual(183.156839765, var_sum, 3)
        

    def test_ZMatrixiExceptions(self):
        #  no space between
        input1 = 'N\nH 1 hn\nH 1 hn 2 hnh\nH 1 hn 2 hnh 3 120.1\nhn 1.2\nhnh 109.5\n'

        # no variables
        input2 = 'N\nH 1 hn\nH 1 hn 2 hnh\nH 1 hn 2 hnh 3 120.1\n'
        input3 = ""

        # missing variable
        input4 = 'N\nH 1 hn\nH 1 hn 2 hnh\nH 1 hn 2 hnh 3 120.1\n\nhn 1.2\n'
 
        self.assertRaises(Exception, cs.ZMatrix, input1)
        self.assertRaises(Exception, cs.ZMatrix, input2)
        self.assertRaises(Exception, cs.ZMatrix, input3)
        self.assertRaises(Exception, cs.ZMatrix, input4)


    def test_get_transform_matrix(self):
        common.ANGSTROMS_TO_BOHRS = 1.8897

        common.DEG_TO_RAD = numpy.pi / 180.
        RAD_TO_DEG = 180. / numpy.pi

        m1 = file2str("CH4.zmt")
        z = cs.ZMatrix(m1)
        m, e = z.get_transform_matrix(z.get_internals())

        print "Testing that the numerical diff errors are small"
        self.assert_(numpy.linalg.norm(e) < 1e-8)

        
        z = cs.ZMatrix(file2str("benzyl.zmt"))
        m, e = z.get_transform_matrix(z.get_internals())

        print "Testing numerical differentiation"
        max_rms_err = 1e-8
        err_msg = "Numerical differentiation RMS error should be less than " + str(max_rms_err) + " but errors were: " + str(e)
        self.assert_(numpy.linalg.norm(e) / len(e) < max_rms_err, err_msg)

        print "Testing generation of forces coordinate system transform matrix"

        zmt_grads_from_benzyl_log = numpy.array([-0.02391, -0.03394, -0.08960, -0.03412, -0.12382, -0.15768, -0.08658, -0.01934, 0.00099, 0.00000, -0.00541, 0.00006, -0.00067, 0.00000, -0.00556, 0.00159, 0.00000, -0.00482, -0.00208])
        xyz_grads_from_benzyl_xyz_log = numpy.array([0.023909846, 0.0, 0.034244932,  0.053971884, 0.0, -0.124058188, -0.004990116, 0.000000000, 0.000806757, -0.005402561, 0.000000000, -0.006533931,  0.008734562, 0.000000000, -0.006763414, -0.002889556, 0.000000000, -0.013862257, -0.072130600, 0.000000000, 0.125686058, -0.005409690, 0.000000000, 0.000029026, -0.002717236, 0.000000000, -0.005359264, 0.002107675, 0.000000000, -0.005198587, 0.004815793, 0., 0.001008869])

        calculated_zmt_grads = numpy.dot(m, xyz_grads_from_benzyl_xyz_log)

        """Gradients in Gaussian are in Hartree/Bohr or radian, but the transform 
        matrix generated by the ZMatrix class has units of angstroms/bohr or 
        degree. For this reason, when comparing Gaussian's gradients in terms of
        z-matrix coordinates (in benzyl.log) with those computed by transforming 
        Gaussian's forces in terms of cartesians (in benzyl_zmt.log), one needs to 
        multiply the angular forces from benzyl.log by the following factor:
        (ANGSTROMS_TO_BOHRS * RAD_TO_DEG). That's what the following two lines 
        are for."""
        for i in [2,4,6,7,8,9,11,12,13,15,16,18]:
            calculated_zmt_grads[i] *= (common.ANGSTROMS_TO_BOHRS)

        self.assertAlmostEqualVec(calculated_zmt_grads, zmt_grads_from_benzyl_log, 1e-3)
#        print "xyz_grads_from_benzyl_log:", xyz_grads_from_benzyl_xyz_log
#        print "zmt_grads_from_benzyl_log:", zmt_grads_from_benzyl_log
#        print "calculated_zmt_grads:", calculated_zmt_grads

    def test_opts(self):
        z = cs.ZMatrix(file2str("butane1.zmt"))
        new_coords = z.get_internals() * 1.15

        z.set_internals(new_coords)

        string_rep = z.xyz_str()

        z.set_calculator(ase.EMT())
        dyn = ase.LBFGS(z)

        print "Running z-matrix optimisation"
        dyn.run(steps=5)

        xyz = cs.XYZ(string_rep)
        xyz.set_calculator(ase.EMT())
        dyn = ase.LBFGS(xyz)

        print "Running cartesian optimisation"
        dyn.run(steps=5)

    def test_Anchoring(self):

        self.assertRaises(cs.ComplexCoordSysException, cs.RotAndTrans, numpy.array([0.,0.,0.,0.,0.,0.]))

        # Generates a series of rotated molecular geometries and views them.
        a = cs.RotAndTrans(numpy.array([1.,0.,0.,0.,1.,1.,1.]))
        z = cs.ZMatrix(file2str("butane1.zmt"), anchor=a)

        print z.get_internals()
        atoms1 = z.atoms.copy()

        alphas = numpy.arange(0., 1., 0.01) * 2 * numpy.pi
        vs     = numpy.arange(0., 1., 0.01)
        geoms_list = []

        for alpha, v in zip(alphas, vs):
            w = numpy.array([numpy.cos(alpha / 2)])

            vec = common.normalise([1,v,-v])
            vec = numpy.sin(alpha / 2) * vec
            q = numpy.hstack([w, vec])
            v = numpy.array([1.,1.,1.])
            a.set(numpy.hstack([q,v]))
            geoms_list.append(z.atoms.copy())

        ase.view(geoms_list)

    def test_ComplexCoordSys(self):

        x = cs.XYZ(file2str("H2.xyz"))

        a_h2o1 = cs.RotAndTrans(numpy.array([1.,0.,0.,0.,3.,1.,1.]), parent=x)
        a_h2o2 = cs.RotAndTrans(numpy.array([1.,0.,0.,0.,1.,1.,1.]), parent=x)
        a_ch4  = cs.RotAndTrans(numpy.array([1.,0.,0.,0.,1.,-1.,1.]), parent=x)

        h2o1 = cs.ZMatrix(file2str("H2O.zmt"), anchor=a_h2o1)
        h2o2 = cs.ZMatrix(file2str("H2O.zmt"), anchor=a_h2o2)
        ch4  = cs.ZMatrix(file2str("CH4.zmt"), anchor=a_ch4)

        parts = [x, h2o1, h2o2, ch4]

        ccs = cs.ComplexCoordSys(parts)
        ccs.set_calculator(aof.ase_gau.Gaussian())

        dyn = ase.LBFGS(ccs)

        list = []
        for i in range(20):
            list.append(ccs.atoms.copy())
            dyn.run(steps=1,fmax=0.01)
            print "Quaternion norms:", a_h2o1.qnorm, a_h2o2.qnorm, a_ch4.qnorm

        list.append(ccs.atoms.copy())

        ase.view(list)

    def form_ccs(self):
        """Forms a complex coordinate system object from a few bits and pieces."""
        x = cs.XYZ(file2str("H2.xyz"))

        a_h2o1 = cs.RotAndTrans(numpy.array([1.,0.,0.,0.,3.,1.,1.]), parent=x)
        a_h2o2 = cs.RotAndTrans(numpy.array([1.,0.,0.,0.,1.,1.,1.]), parent=x)
        a_ch4  = cs.RotAndTrans(numpy.array([1.,0.,0.,0.,1.,-1.,1.]), parent=x)

        h2o1 = cs.ZMatrix(file2str("H2O.zmt"), anchor=a_h2o1)
        h2o2 = cs.ZMatrix(file2str("H2O.zmt"), anchor=a_h2o2)
        ch4  = cs.ZMatrix(file2str("CH4.zmt"), anchor=a_ch4)

        parts = [x, h2o1, h2o2, ch4]

        ccs = cs.ComplexCoordSys(parts)

        return ccs, x, h2o1, h2o2, ch4, a_h2o1, a_h2o2, a_ch4

    def test_ComplexCoordSys_var_mask(self):

        print "Running tests with masking of variables"

        #ch4  = cs.ZMatrix(file2str("CH4.zmt"))
        ccs, x, h2o1, h2o2, ch4, a_h2o1, a_h2o2, a_ch4 = self.form_ccs()

        ccs.set_calculator(aof.ase_gau.Gaussian())

        m = [True for i in range(0)] + [True for i in range(ccs.dims)]
        parts = [x, h2o1, a_h2o1, h2o2, a_h2o2, ch4, a_ch4]
        dims = [p._dims for p in parts]
        print dims
        torf = lambda d, f: [f for i in range(d)]
        fs = [False, True, True, True, False, False, False]
        m1 = [torf(d,f) for d,f in zip(dims, fs)]

        print m1
        m = [m_ for d,f in zip(dims, fs) for m_ in torf(d,f)]

        print m
        
        mask = numpy.array(m)
        ccs.set_var_mask(mask)

        dyn = ase.LBFGS(ccs)

        list = []
        for i in range(20):
            list.append(ccs.atoms.copy())
            dyn.run(steps=1,fmax=0.01)
            print "Quaternion norms:", a_h2o1.qnorm, a_h2o2.qnorm, a_ch4.qnorm

        list.append(ccs.atoms.copy())

        ase.view(list)

    def test_ComplexCoordSys2(self):

        x = cs.XYZ(file2str("H2.xyz"))
        a = cs.RotAndTrans(numpy.array([1.,0.,0.,0.,3.,1.,1.]), parent=x)
        z = cs.ZMatrix(file2str("butane1.zmt"), anchor=a)

        parts = [x, z]

        ccs = cs.ComplexCoordSys(parts)
        ccs.set_calculator(aof.ase_gau.Gaussian())

        print ccs.get_potential_energy()
        print ccs.get_forces()

        dyn = ase.LBFGS(ccs)

        list = []
        for i in range(40):
            dyn.run(steps=1,fmax=0.01)
            list.append(ccs.atoms.copy())

        ase.view(list)

    def test_CoordSys_pickling(self):

        print "Creating a Z-matrix, pickling it, then performing an dientical"
        print "optimisation on each one, then checking that the forces are identical."
        calc = ase.EMT()

        z1 = cs.ZMatrix(file2str("butane1.zmt"))

        s = pickle.dumps(z1)
        z1.set_calculator(calc)
        opt = ase.LBFGS(z1)
        opt.run(steps=4)

        forces1 = z1.get_forces()

        z2 = pickle.loads(s)
        z2.set_calculator(calc)

        opt = ase.LBFGS(z2)
        opt.run(steps=4)

        forces2 = z2.get_forces()
        self.assert_((forces1 == forces2).all())

    def test_ComplexCoordSys_pickling(self):
      
        calc = ase.EMT()

        x = cs.XYZ(file2str("H2.xyz"))
        a = cs.RotAndTrans(numpy.array([1.,0.,0.,0.,3.,1.,1.]), parent=x)
        z = cs.ZMatrix(file2str("butane1.zmt"), anchor=a)

        parts = [x, z]

        ccs = cs.ComplexCoordSys(parts)
        ccs.set_calculator(calc)
        forces0 = ccs.get_forces()

        ccs_pickled = pickle.loads(pickle.dumps(ccs))
        ccs_pickled.set_calculator(calc)

        forces_pickled0 = ccs.get_forces()

        dyn = ase.LBFGS(ccs_pickled)
        dyn.run(steps=3)

        forces_pickled1 = ccs_pickled.get_forces()

        dyn = ase.LBFGS(ccs)
        dyn.run(steps=3)

        forces1 = ccs.get_forces()

        self.assert_((forces0 == forces_pickled0).all())
        self.assert_((forces1 == forces_pickled1).all())
        self.assert_((forces0 != forces1).any())



    def test_to_xyz_conversion(self):
        pass

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(TestZMatrixAndAtom)

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([TestZMatrixAndAtom("test_ComplexCoordSys_var_mask")]))


