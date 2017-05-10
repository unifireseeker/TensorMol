"""
The Units chosen are Angstrom * Fs.
I convert the force outside from kcal/(mol angstrom) to Joules/(mol angstrom)
kcal/angstrom. = 4.184e+13 joules/meter  = 4184 joules/angstrom
Kb = 8.314 J/Mol K
"""

from Sets import *
from TFManage import *
from Electrostatics import *

def VelocityVerletstep(f_, a_, x_, v_, m_, dt_ ):
	""" A Velocity Verlet Step
	Args:
	f_: The force function (returns Joules/Angstrom)
	a_: The acceleration at current step. (A^2/fs^2)
	x_: Current coordinates (A)
	v_: Velocities (A/fs)
	m_: the mass vector. (kg)
	"""
	x = x_ + v_*dt_ + (1./2.)*a_*dt_*dt_
	a = pow(10.0,-10.0)*np.einsum("ax,a->ax", f_(x), 1.0/m_) # m^2/s^2 => A^2/Fs^2
	#print "dt", dt_ # fs
	#print "a", a
	#print "v", v_
	v = v_ + (1./2.)*(a_+a)*dt_
	return x,v,a

def KineticEnergy(v_, m_):
	""" The KineticEnergy
	Args:
		The masses are in kg.
		v_: Velocities (A/fs)
		m_: the mass vector. (kg/mol)
	Returns:
		The kinetic energy per atom (J/mol)
	"""
	return (1./2.)*np.dot(np.einsum("ia,ia->i",v_,v_)*pow(10.0,10.0),m_)/len(m_)

class Thermostat:
	def __init__(self,m_,v_):
		"""
		Velocity Verlet step with a Rescaling Thermostat
		"""
		self.N = len(m_)
		self.m = m_.copy()
		self.T = PARAMS["MDTemp"]  # Length of NH chain.
		self.kT = 8.314*pow(10.0,-10.0)*self.T # energy units here are kg (A/fs)^2
		self.tau = 30*PARAMS["MDdt"]
		self.name = "Rescaling"
		print "Using ", self.name, " thermostat at ",self.T, " degrees Kelvin"
		self.Rescale(v_)
		return
	def step(self,f_, a_, x_, v_, m_, dt_ ):
		x = x_ + v_*dt_ + (1./2.)*a_*dt_*dt_
		a = pow(10.0,-10.0)*np.einsum("ax,a->ax", f_(x), 1.0/m_) # m^2/s^2 => A^2/Fs^2
		v = v_ + (1./2.)*(a_+a)*dt_
		Teff = (2./3.)*KineticEnergy(v,self.m)/8.314
		v *= np.sqrt(self.T/Teff)
		return x,v,a
	def Rescale(self,v_):
		# Do this elementwise otherwise H's blow off.
		for i in range(self.N):
			Teff = (2.0/(3.0*8.314))*pow(10.0,10.0)*(1./2.)*self.m[i]*np.einsum("i,i",v_[i],v_[i])
			v_[i] *= np.sqrt(self.T/Teff)
		return

class NoseThermostat(Thermostat):
	def __init__(self,m_,v_):
		"""
		Velocity Verlet step with a Nose-Hoover Thermostat.
		"""
		self.m = m_.copy()
		self.N = len(m_)
		self.T = PARAMS["MDTemp"]  # Length of NH chain.
		self.kT = 8.314*pow(10.0,-10.0)*self.T # energy units here are kg (A/fs)^2
		self.tau = 30*PARAMS["MDdt"]
		self.Q = self.kT*self.tau*self.tau
		self.eta = 0.0
		self.name = "Nose"
		self.Rescale(v_)
		print "Using ", self.name, " thermostat at ",self.T, " degrees Kelvin"
		return
	def step(self,f_, a_, x_, v_, m_, dt_ ):
		"""
		http://www2.ph.ed.ac.uk/~dmarendu/MVP/MVP03.pdf
		"""
		x = x_ + v_*dt_ + (1./2.)*(a_ - self.eta*v_)*dt_*dt_
		vdto2 = v_ + (1./2.)*(a_ - self.eta*v_)*dt_
		a = pow(10.0,-10.0)*np.einsum("ax,a->ax", f_(x), 1.0/m_) # m^2/s^2 => A^2/Fs^2
		ke = (1./2.)*np.dot(np.einsum("ia,ia->i",v_,v_),m_)
		etadto2 = self.eta + (dt_/(2.*self.Q))*(ke - (((3.*self.N+1)/2.))*self.kT)
		kedto2 = (1./2.)*np.dot(np.einsum("ia,ia->i",vdto2,vdto2),m_)
		self.eta = etadto2 + (dt_/(2.*self.Q))*(kedto2 - (((3.*self.N+1)/2.))*self.kT)
		v = (vdto2 + (dt_/2.)*a)/(1 + (dt_/2.)*self.eta)
		return x,v,a

class NosePerParticleThermostat(Thermostat):
	def __init__(self,m_,v_):
		"""
		This
		"""
		self.m = m_.copy()
		self.N = len(m_)
		self.T = PARAMS["MDTemp"]  # Length of NH chain.
		self.kT = 8.314*pow(10.0,-10.0)*self.T # energy units here are kg (A/fs)^2
		self.tau = 25*PARAMS["MDdt"]
		self.Q = self.kT*self.tau*self.tau
		self.eta = np.zeros(self.N)
		self.name = "NosePerParticle"
		self.Rescale(v_)
		print "Using ", self.name, " thermostat at ",self.T, " degrees Kelvin"
		return
	def step(self,f_, a_, x_, v_, m_, dt_ ):
		"""
		http://www2.ph.ed.ac.uk/~dmarendu/MVP/MVP03.pdf
		"""
		x = x_ + v_*dt_ + (1./2.)*(a_ - np.einsum("i,ij->ij",self.eta,v_))*dt_*dt_
		vdto2 = v_ + (1./2.)*(a_ - np.einsum("i,ij->ij",self.eta,v_))*dt_
		a = pow(10.0,-10.0)*np.einsum("ax,a->ax", f_(x), 1.0/m_) # m^2/s^2 => A^2/Fs^2
		kes = (1./2.)*np.einsum("i,i->i",np.einsum("ia,ia->i",v_,v_),m_)
		etadto2 = self.eta + (dt_/(2.*self.Q))*(kes - (((3.*self.N+1)/2.))*self.kT)
		kedto2s = (1./2.)*np.einsum("i,i->i",np.einsum("ia,ia->i",vdto2,vdto2),m_)
		self.eta = etadto2 + (dt_/(2.*self.Q))*(kedto2s - (((3.*self.N+1)/2.))*self.kT)
		v = np.einsum("ij,i->ij",(vdto2 + (dt_/2.)*a),1.0/(1 + (dt_/2.)*self.eta))
		return x,v,a

class NoseChainThermostat(Thermostat):
	def __init__(self,m_,v_):
		"""
		Velocity Verlet step with a Nose-Hoover Chain Thermostat.
		Based on Appendix A of martyna 1996
		http://dx.doi.org/10.1080/00268979600100761
		Args:
			x_: an example of system positions.
			m_: system masses.
			PARAMS["MNHChain"]: depth of the Nose Hoover Chain
			PARAMS["MDTemp"]: Temperature of the Thermostat.
			PARAMS["MDdt"]: Timestep of the dynamics.
		"""
		self.M = PARAMS["MNHChain"] # Depth of NH chain.
		self.N = len(v_) # Number of particles.
		self.Nf = len(v_)*3 # Number of Degrees of freedom.
		self.T = PARAMS["MDTemp"]  # Length of NH chain.
		self.kT = 8.314*pow(10.0,-10.0)*self.T # energy units here are kg (A/fs)^2
		self.GNKT = self.Nf*self.kT
		self.nc = 2 # nc Number of Trotterizations To be increased if Q is large.
		self.ny = 3# nys (eq. 29 of Martyna. number of quadrature points within step.)
		self.wj = np.zeros(self.ny)
		if (self.ny == 3):
			self.wj[0],self.wj[1],self.wj[2] = (1./(2. - np.power(2.,1./3.))),(1.-2.*(1./(2. - np.power(2.,1./3.)))),(1./(2. - np.power(2.,1./3.)))
		elif (self.ny == 5):
			self.wj[0] = (1./(4. - np.power(4.,1./3.)))
			self.wj[1] = (1./(4. - np.power(4.,1./3.)))
			self.wj[2] = 1.-4.*self.wj[0]
			self.wj[3] = (1./(4. - np.power(4.,1./3.)))
			self.wj[4] = (1./(4. - np.power(4.,1./3.)))
		self.tau = 30*PARAMS["MDdt"]
		self.dt = PARAMS["MDdt"]
		self.dt2 = self.dt/2.
		self.dt22 = self.dt*self.dt/2.
		self.Qs = None # Chain Masses.
		self.MartynaQs() # assign the chain masses.
		self.eta = np.zeros(self.M) # Chain positions.
		self.Veta = np.zeros(self.M) # Chain velocities
		self.Geta = np.zeros(self.M) # Chain forces
		self.name = "NoseHooverChain"
		self.Rescale(v_)
		print "Using ", self.name, " thermostat at ",self.T, " degrees Kelvin"
		return

	def MartynaQs(self):
		if (self.M==0):
			return
		self.Qs = np.ones(self.M)*self.kT*self.tau*self.tau
		self.Qs[0] = 3.*self.N*self.kT*self.tau*self.tau
		return

	def step(self,f_, a_, x_, v_, m_, dt_ ):
		v = self.IntegrateChain(a_, x_, v_, m_, dt_) # half step the chain.
		# Get KE of the chain.
		print "Energies of the system... ", self.ke(v_,m_), " Teff ", (2./3.)*self.ke(v_,m_)*pow(10.0,10.0)/8.314/self.N
		print "Energies along the chain... Desired:", (3./2.)*self.kT
		for i in range(self.M):
			print self.Veta[i]*self.Veta[i]*self.Qs[i]/2.
		v = v + self.dt2*a_
		x = x_ + self.dt*v
		a = pow(10.0,-10.0)*np.einsum("ax,a->ax", f_(x), 1.0/m_) # m^2/s^2 => A^2/Fs^2
		v = v + self.dt2*a
		v = self.IntegrateChain(a, x_, v, m_, dt_) # half step the chain.
		return x, v, a

	def ke(self,v_,m_):
		return (1./2.)*np.dot(np.einsum("ia,ia->i",v_,v_),m_)

	def IntegrateChain(self, a_, x_, v_, m_, dt_ ):
		"""
		The Nose Hoover chain is twice trotterized in Martyna's subroutine
		So this evolves the chain a half-step, and updates v_
		"""
		if (self.M==0):
			return v_
		ake = self.ke(v_,m_) # in kg (A^2/Fs^2)
		# Update thermostat forces.
		self.Geta[0]  = (2.*ake - self.GNKT) / self.Qs[0]
		scale = 1.0
		for k in range(self.nc):
			for j in range(self.ny):
				# UPDATE THE THERMOSTAT VELOCITIES.
				wdtj2 = (self.wj[j]*self.dt/self.nc)/2.
				wdtj4 = wdtj2/2.
				wdtj8 = wdtj4/2.
				self.Veta[-1] += self.Geta[-1]*wdtj4
				for i in range(self.M-1)[::-1]:
					AA = np.exp(-wdtj8*self.Veta[i+1])
					self.Veta[i] = self.Veta[i]*AA*AA + wdtj4*self.Geta[i]*AA
				# Update the particle velocities.
				AA = np.exp(-wdtj2*self.Veta[1])
				scale *= AA
				self.Geta[0] = (scale*scale*2.0*ake - self.GNKT)/self.Qs[0]
				# Update the Thermostat Positions.
				for i in range(self.M):
					self.eta[i] += self.Veta[i]*wdtj2
				# Update the thermostat velocities
				for i in range(self.M-1):
					AA = np.exp(-wdtj8*self.Veta[i+1])
					self.Veta[i] = self.Veta[i]*AA*AA + wdtj4*self.Geta[i]*AA
					self.Geta[i+1] = (self.Qs[i]*self.Veta[i]*self.Veta[i] - self.kT)/self.Qs[i+1]
				self.Veta[-1] += self.Geta[-1] * wdtj4
		print "eta",self.eta
		print "Meta",self.Qs
		print "Veta",self.Veta
		print "Geta",self.Geta
		return v_*scale

class VelocityVerlet:
	def __init__(self,f_,g0_, name_ =""):
		"""
		Molecular dynamics
		Args:
			f_: a force routine
			m0_: initial molecule.
			PARAMS["MDMaxStep"]: Number of steps to take.
			PARAMS["MDTemp"]: Temperature to initialize or Thermostat to.
			PARAMS["MDdt"]: Timestep.
			PARAMS["MDV0"]: Sort of velocity initialization (None, or "Random")
			PARAMS["MDLogVelocity"]: Write MD velocities.
			PARAMS["MDLogTrajectory"]: Write MD Trajectory.
		Returns:
			A reaction path.
		"""
		self.name = name_
		self.maxstep = PARAMS["MDMaxStep"]
		self.T = PARAMS["MDTemp"]
		self.dt = PARAMS["MDdt"]
		self.ForceFunction = f_
		self.t = 0.0
		self.KE = 0.0
		self.atoms = g0_.atoms.copy()
		self.m = np.array(map(lambda x: ATOMICMASSES[x],self.atoms))
		self.natoms = len(self.atoms)
		self.x = g0_.coords.copy()
		self.v = np.zeros(self.x.shape)
		self.a = np.zeros(self.x.shape)
		if (PARAMS["MDV0"]=="Random"):
			self.v = np.random.randn(*self.x.shape)
			Tstat = Thermostat(self.m, self.v) # Will rescale self.v appropriately.

		self.Tstat = None
		if (PARAMS["MDThermostat"]=="Rescaling"):
			self.Tstat = Thermostat(self.m,self.v)
		elif (PARAMS["MDThermostat"]=="Nose"):
			self.Tstat = NoseThermostat(self.m,self.v)
		elif (PARAMS["MDThermostat"]=="NosePerParticle"):
			self.Tstat = NosePerParticleThermostat(self.m,self.v)
		elif (PARAMS["MDThermostat"]=="NoseHooverChain"):
			self.Tstat = NoseChainThermostat(self.m, self.v)
		else:
			print "Unthermostated Velocity Verlet."
		return

	def WriteTrajectory(self):
		m=Mol(self.atoms,self.x)
		m.properties["Time"]=self.t
		m.properties["KineticEnergy"]=self.KE
		m.WriteXYZfile("./results/", "MDTrajectory"+self.name)
		return

	def Prop(self):
		"""
		Propagate VelocityVerlet
		"""
		step = 0
		while(step < self.maxstep):
			self.t = step*self.dt
			self.KE = KineticEnergy(self.v,self.m)
			Teff = (2./3.)*self.KE/8.314
			if (PARAMS["MDThermostat"]==None):
				self.x , self.v, self.a = VelocityVerletstep(self.ForceFunction, self.a, self.x, self.v, self.m, self.dt)
			else:
				self.x , self.v, self.a = self.Tstat.step(self.ForceFunction, self.a, self.x, self.v, self.m, self.dt)
			if (step%3==0 and PARAMS["MDLogTrajectory"]):
				self.WriteTrajectory()
			step+=1
			LOGGER.info("Step: %i time: %.1f(fs) <KE>(J): %.5f Teff(K): %.5f", step, self.t, self.KE,Teff)
		if PARAMS["MDLogVelocity"] == True:
			return velo_his
		else:
			return

class IRTrajectory(VelocityVerlet):
	def __init__(self,f_,q_,g0_,name_=str(0)):
		"""
		A specialized sort of dynamics which is appropriate for obtaining IR spectra at
		Zero temperature.

		Args:
			f_: a function which yields the force
			q_: a function which yields the charge.
			g0_: an initial geometry.
			PARAMS["MDFieldVec"]
			PARAMS["MDFieldAmp"]
			PARAMS["MDFieldT0"] = 3.0
			PARAMS["MDFieldTau"] = 1.2 #1.2 fs pulse.
			PARAMS["MDFieldFreq"] = 1/1.2 # 700nm light is about 1/1.2 fs.
		"""
		VelocityVerlet.__init__(self,f_, g0_, name_)
		self.EField = np.zeros(3)
		self.IsOn = False
		self.qs = None
		self.FieldVec = PARAMS["MDFieldVec"]
		self.FieldAmp = PARAMS["MDFieldAmp"]
		self.FieldFreq = PARAMS["MDFieldFreq"]
		self.Tau = PARAMS["MDFieldTau"]
		self.TOn = PARAMS["MDFieldT0"]
		self.UpdateCharges = PARAMS["MDUpdateCharges"]
		self.FieldFreeForce = f_
		self.ChargeFunction = q_
		self.q0 = self.ChargeFunction(self.x)
		self.Mu0 = Dipole(self.x, self.ChargeFunction(self.x))
		self.mu_his = None

	def Pulse(self,t_):
		"""
		\delta pulse of duration
		"""
		sin_part = (np.sin(2.0*3.1415*self.FieldFreq*t_))
		exp_part = (1.0/np.sqrt(2.0*3.1415*self.Tau*self.Tau))*(np.exp(-1.0*np.power(t_-self.TOn,2.0)/(2.0*self.Tau*self.Tau)))
		amp = self.FieldAmp*sin_part*exp_part
		if (np.abs(amp) > np.power(10.0,-12.0)):
			return self.FieldVec*amp, True
		else:
			return np.zeros(3), False

	def ForcesWithCharge(self,x_):
		if (self.IsOn):
			FFForce = self.FieldFreeForce(x_)
			# ElectricFieldForce Is in units of Hartree/angstrom.
			# and must be converted to kg*Angstrom/(Fs^2)
			ElecForce = 4184.0*np.power(10.0,10.0)*ElectricFieldForce(self.qs, self.EField)
			print "Field Free Force", FFForce
			print "ElecForce Force", ElecForce
			return RemoveInvariantForce(x_, FFForce + ElecForce, self.m)
		else:
			return RemoveInvariantForce(x_, self.FieldFreeForce(x_), self.m)

	def WriteTrajectory(self):
		m=Mol(self.atoms,self.x)
		m.properties["Time"]=self.t
		m.properties["KineticEnergy"]=self.KE
		#m.properties["Charges"]=self.qs
		m.WriteXYZfile("./results/", "MDTrajectory"+self.name)
		return

	def Prop(self):
		self.mu_his = np.zeros((self.maxstep, 6)) # time Dipoles Energy
		step = 0
		while(step < self.maxstep):
			self.t = step*self.dt
			self.KE = KineticEnergy(self.v,self.m)
			Teff = (2./3.)*self.KE/8.314

			self.EField, self.IsOn = self.Pulse(self.t)
			if (self.UpdateCharges and not self.IsOn):
				self.qs = self.ChargeFunction(self.x)
			else:
				self.qs = self.q0
			self.Mu = Dipole(self.x, self.qs) - self.Mu0
			print self.Mu
			self.mu_his[step,0] = self.t
			self.mu_his[step,1:4] = self.Mu
			self.mu_his[step,5] = self.KE

			self.x , self.v, self.a = VelocityVerletstep(self.ForcesWithCharge, self.a, self.x, self.v, self.m, self.dt)
			if (step%3==0 and PARAMS["MDLogTrajectory"]):
				self.WriteTrajectory()
			if (step%100==0):
				np.savetxt("./results/"+"MDLog"+self.name+".txt",self.mu_his)

			step+=1
			LOGGER.info("Step: %i time: %.1f(fs) <KE>(J): %.5f Teff(K): %.5f Mu: (%f,%f,%f)", step, self.t, self.KE, Teff, self.Mu[0], self.Mu[1], self.Mu[2])
		return
