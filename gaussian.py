"""This module defines an ASE interface to Gaussian.
"""

import os
import subprocess
import shutil

import numpy

from ase.data import chemical_symbols


class Gaussian:
    """Class for doing Gaussian calculations."""
    def __init__(self, jobname="gaussjob", 
            method="HF", 
            basis="3-21G", 
            gau_command="g03", 
            charge=0, 
            mult=1,
            nprocs=1,
            chkpoint=None):

        """Construct Gaussian-calculator object.

        Parameters
        ==========
        jobname: str
            Prefix to use for filenames

        method: str, e.g. b3lyp, ROHF, etc.
        basis:  str, e.g. 6-31G(d)
            level of theory string is formed from method/basis

        gau_command: str
            command to run gaussian, e.g. g03, g98, etc.

        nprocs: int
            number of processors to use (shared memory)

        chkpoint: str
            if specified, an initial checkpoint file to read a guess in from.
            Note: it's probably possible to confuse the driver by supplying a 
            checkpoint for a significantly different structure.
        
        """
        
        self.jobname = jobname
        self.method = method
        self.basis = basis
        self.charge = charge
        self.mult = mult

        if os.system("which " + gau_command) != 0:
            raise GaussDriverError("Executable " + gau_command + " not found in path.")
        self.gau_command = gau_command
        self.nprocs = nprocs
        assert nprocs > 0
        assert type(nprocs) == int

        if chkpoint != None and not os.path.isfile(chkpoint):
            raise GaussDriverError("File " + chkpoint + " is not a propper file or does not exist")
        self.chkpoint = chkpoint

        # see function generate_header() also
        self.max_aggression = 1
        self.runs = 0

    def update(self, atoms):
        """If Necessary, runs calculation."""

        # test whether atoms object has changed
        if (self.runs < 1 or
            len(self.numbers) != len(atoms) or
            (self.numbers != atoms.get_atomic_numbers()).any()):
            self.initialize(atoms)
            self.calculate(atoms)

        # test whether positions of atoms have changed
        elif (self.positions != atoms.get_positions()).any():
            self.calculate(atoms)

    def generate_header(self, aggression=0):

        params = []
        if aggression == 0:

            if self.runs > 0:
                params.append("guess=read")
            elif self.chkpoint != None:
                shutil.copyfile(self.chkpoint, self.jobname + ".chk")
                params.append("guess=read")

        elif aggression == 1:
            print "Gaussian: aggression =", aggression
            params.append("scf=qc")
        else:
            raise GaussDriverError("Unsupported aggression level: " + str(aggression))

        params_str = ' '.join(params)

        job_header = "%%chk=%s.chk\n%%nprocs=%d\n# %s/%s %s force\n\nGenerated by ASE Gaussian driver\n\n%d %d\n" \
            % (self.jobname, self.nprocs, self.method, self.basis, params_str, self.charge, self.mult)

        return job_header

    def initialize(self, atoms):
        self.numbers = atoms.get_atomic_numbers().copy()
        self.runs = 0
        self.converged = False
        
    def get_potential_energy(self, atoms, force_consistent=False):
        self.update(atoms)

        return self.__e

    def get_forces(self, atoms):
        self.update(atoms)
        return self.__forces.copy()
    
    def get_stress(self, atoms):
        raise NotImplementedError

    def calculate(self, atoms):
        self.positions = atoms.get_positions().copy()
        inputfile = self.jobname + ".com"

        list = ['%-2s %22.15f %22.15f %22.15f' % (s, x, y, z) for s, (x, y, z) in zip(atoms.get_chemical_symbols(), atoms.get_positions())]
        geom_str = '\n'.join(list) + '\n\n'

        parse_result = None
        ag = 0
        while parse_result == None:
            if ag > self.max_aggression:
                raise GaussDriverError("Unable to converge SCF for geometry and settings in " + inputfile)

            job_str = self.generate_header(aggression=ag) + geom_str
            f = open(inputfile, "w")
            f.write(job_str)
            f.close()

            args = [self.gau_command, inputfile]
            command = " ".join(args)

            p = subprocess.Popen(command, shell=True)
            sts = os.waitpid(p.pid, 0)
            parse_result = self.read()

            # next attempt will have higher aggression
            ag += 1

        self.__e, self.__forces = parse_result

        self.converged = True
        self.runs += 1
        
    def read(self):
        """Read results from Gaussian's text-output file."""
        logfilename = self.jobname + '.log'
        logfile = open(logfilename, 'r')

        line = logfile.readline()

        forces = []
        e = None
        while line != '':
            if line.find("SCF Done") != -1:
                e = line.split()[4]
                e = float(e)
            elif line[37:43] == "Forces":
                header = logfile.readline()
                dashes = logfile.readline()
                line = logfile.readline()
                while line != dashes:
                    n,nuclear,Fx,Fy,Fz = line.split()
                    forces.append([float(Fx),float(Fy),float(Fz)])
                    line = logfile.readline()
            elif line.find("Convergence failure -- run terminated") != -1:
                return None

            line = logfile.readline()

        if e == None or forces == []:
            raise GaussDriverError("File not parsed, check " + logfilename)

        forces = numpy.array(forces)
        return e, forces

class GaussDriverError(Exception):
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
        return self.msg


