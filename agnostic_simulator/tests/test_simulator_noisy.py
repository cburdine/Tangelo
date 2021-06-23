"""
    A test class to check that the features related to noisy simulation are working as expected.
"""

import unittest

from agnostic_simulator import Gate, Circuit, Simulator, backend_info
from agnostic_simulator.noisy_simulation import NoiseModel, get_qiskit_noise_dict

# Noisy simulation: circuits, noise models, references
cn1 = Circuit([Gate('X', target=0)])
cn2 = Circuit([Gate('CNOT', target=1, control=0)])

nmp, nmd, nmc = NoiseModel(), NoiseModel(), NoiseModel()
# nmp: pauli noise with equal probabilities, on X and CNOT gates
nmp.add_quantum_error("X", 'pauli', [1 / 3] * 3)
nmp.add_quantum_error("CNOT", 'pauli', [1 / 3] * 3)
# nmd: depol noise with prob 1. on X and CNOT gates
nmd.add_quantum_error("X", 'depol', 1.)
nmd.add_quantum_error("CNOT", 'depol', 1.)
# nmc: cumulates 2 Pauli noises (here, is equivalent to no noise, as it applies Y twice when X is ran)
nmc.add_quantum_error("X", 'pauli', [0., 1., 0.])
nmc.add_quantum_error("X", 'depol', 4/3)

ref_pauli1 = {'1': 1 / 3, '0': 2 / 3}
ref_pauli2 = {'01': 2 / 9, '11': 4 / 9, '10': 2 / 9, '00': 1 / 9}
ref_depol1 = {'1': 1 / 2, '0': 1 / 2}
ref_depol2 = {'01': 1 / 4, '11': 1 / 4, '10': 1 / 4, '00': 1 / 4}
ref_cumul = {'0': 1/3, '1': 2/3}


def assert_freq_dict_almost_equal(d1, d2, atol):
    """ Utility function to check whether two frequency dictionaries are almost equal, for arbitrary tolerance """
    if d1.keys() != d2.keys():
        raise AssertionError("Dictionary keys differ. Frequency dictionaries are not almost equal.\n"
                             f"d1 keys: {d1.keys()} \nd2 keys: {d2.keys()}")
    else:
        for k in d1.keys():
            if abs(d1[k] - d2[k]) > atol:
                raise AssertionError(f"Dictionary entries beyond tolerance {atol}: \n{d1} \n{d2}")
    return True


class TestSimulate(unittest.TestCase):

    def test_noisy_simulation_not_supported(self):
        """
            Ensures that an error is returned if user attempts to run noisy simulation on a backend that does
            not support it as part of this package.
        """
        for b, s in backend_info.items():
            if not s['noisy_simulation']:
                self.assertRaises(ValueError, Simulator, target=b, n_shots=1, noise_model=True)

    def test_cannot_cumulate_same_noise_same_gate(self):
        """ Ensures an error is returned if user attempts to cumulate the same type of noise on the same gate """
        nm = NoiseModel()
        nm.add_quantum_error('X', 'depol', 0.2)
        self.assertRaises(ValueError, nm.add_quantum_error, 'X', 'depol', 0.3)

    def test_unsupported_noise_channel(self):
        """ Ensures an error is returned if user attempts to user an unsupported noise channel """
        nm = NoiseModel()
        self.assertRaises(ValueError, nm.add_quantum_error, 'X', 'incorrect_input', 0.3)

    def test_incorrect_arguments(self):
        """ Ensures an error is returned if noise parameters are incorrect """
        nm = NoiseModel()
        self.assertRaises(ValueError, nm.add_quantum_error, 'X', 'pauli', 0.3)
        self.assertRaises(ValueError, nm.add_quantum_error, 'X', 'depol', 1)
        self.assertRaises(ValueError, nm.add_quantum_error, 'X', 'depol', [0.3, 0.2, 0.1])

    # TODO: replace the noise channel name by one supported by agnostic simulator, but not with qiskit backend later
    def test_unsupported_noise_channel_qiskit(self):
        """ Ensures an error is returned if user attempts to user an unsupported noise channel, for qiskit """
        nm = NoiseModel()
        self.assertRaises(ValueError, nm.add_quantum_error, 'X', 'dummy', 0.3)

    def test_qiskit_noise_dictionary_rotations(self):
        """ Generate noise dictionary using qiskit gates as keys. Map rotation gates to U-gates with no redundancy
         Ensure results as expected."""

        nt, np = 'pauli', [0.5, 0.25, 0.25]
        nm = NoiseModel()
        for g in {"RX", "RY", "RZ"}:
            nm.add_quantum_error(g, nt, np)

        qnd = get_qiskit_noise_dict(nm)
        for g in {'u1', 'u2', 'u3'}:
            assert(g in qnd)
            assert(qnd[g] == [(nt, np)])

    def test_noisy_simulation_qulacs(self):
        """
            Test noisy simulation through qulacs.
            Currently tested: pauli noise, depolarization noise (1 and 2 qubit gates)
        """

        # Pauli noise for one- and two-qubit gates. Circuits are only a X gate, or just a CNOT gate.
        s_nmp = Simulator(target='qulacs', n_shots=10**6, noise_model=nmp)
        res_pauli1, _ = s_nmp.simulate(cn1)
        assert_freq_dict_almost_equal(res_pauli1, ref_pauli1, 1e-2)
        res_pauli2, _ = s_nmp.simulate(cn2)
        assert_freq_dict_almost_equal(res_pauli2, ref_pauli2, 1e-2)

        # Depol noise for one- and two-qubit gates. Circuits are only a X gate or just a CNOT gate.
        s_nmd = Simulator(target='qulacs', n_shots=10**6, noise_model=nmd)
        res_depol1, _ = s_nmd.simulate(cn1)
        assert_freq_dict_almost_equal(res_depol1, ref_depol1, 1e-2)
        res_depol2, _ = s_nmd.simulate(cn2)
        assert_freq_dict_almost_equal(res_depol2, ref_depol2, 1e-2)

        # Cumulate several noises on a given gate (here noise simplifies to identity)
        s_nmc = Simulator(target='qulacs', n_shots=10**6, noise_model=nmc)
        res_cumul, _ = s_nmc.simulate(cn1)
        assert_freq_dict_almost_equal(res_cumul, ref_cumul, 1e-2)

    def test_noisy_simulation_qiskit(self):
        """
            Test noisy simulation through qiskit.
            Currently tested: pauli noise, depolarization noise (1 and 2 qubit gates)
        """

        # Pauli noise for one- and two-qubit gates. Circuits are only a X gate, or just a CNOT gate.
        s_nmp = Simulator(target='qiskit', n_shots=10**6, noise_model=nmp)
        res_pauli1, _ = s_nmp.simulate(cn1)
        assert_freq_dict_almost_equal(res_pauli1, ref_pauli1, 1e-2)
        res_pauli2, _ = s_nmp.simulate(cn2)
        assert_freq_dict_almost_equal(res_pauli2, ref_pauli2, 1e-2)

        # Depol noise for one- and two-qubit gates. Circuits are only a X gate or just a CNOT gate.
        s_nmd = Simulator(target='qiskit', n_shots=10**6, noise_model=nmd)
        res_depol1, _ = s_nmd.simulate(cn1)
        assert_freq_dict_almost_equal(res_depol1, ref_depol1, 1e-2)
        res_depol2, _ = s_nmd.simulate(cn2)
        assert_freq_dict_almost_equal(res_depol2, ref_depol2, 1e-2)

        # Cumulate several noises on a given gate (here noise simplifies to identity)
        s_nmp = Simulator(target='qiskit', n_shots=10**6, noise_model=nmc)
        res_cumul, _ = s_nmp.simulate(cn1)
        assert_freq_dict_almost_equal(res_cumul, ref_cumul, 1e-2)

    def test_noisy_simulation_cirq(self):
        """
            Test noisy simulation through cirq.
            Currently tested: pauli noise, depolarization noise (1 and 2 qubit gates)
        """

        # Pauli noise for one- and two-qubit gates. Circuits are only a X gate, or just a CNOT gate.
        s_nmp = Simulator(target='cirq', n_shots=10**6, noise_model=nmp)
        res_pauli1, _ = s_nmp.simulate(cn1)
        assert_freq_dict_almost_equal(res_pauli1, ref_pauli1, 1e-2)
        res_pauli2, _ = s_nmp.simulate(cn2)
        assert_freq_dict_almost_equal(res_pauli2, ref_pauli2, 1e-2)

        # Depol noise for one- and two-qubit gates. Circuits are only a X gate or just a CNOT gate.
        s_nmd = Simulator(target='cirq', n_shots=10**6, noise_model=nmd)
        res_depol1, _ = s_nmd.simulate(cn1)
        assert_freq_dict_almost_equal(res_depol1, ref_depol1, 1e-2)
        res_depol2, _ = s_nmd.simulate(cn2)
        assert_freq_dict_almost_equal(res_depol2, ref_depol2, 1e-2)

        # Cumulate several noises on a given gate (here noise simplifies to identity)
        s_nmc = Simulator(target='cirq', n_shots=10**6, noise_model=nmc)
        res_cumul, _ = s_nmc.simulate(cn1)
        assert_freq_dict_almost_equal(res_cumul, ref_cumul, 1e-2)


if __name__ == "__main__":
    unittest.main()