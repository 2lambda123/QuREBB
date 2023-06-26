import numpy as np
import qutip as qt
import numbers
from copy import deepcopy

class NQobj(qt.Qobj):
    """This Named Qobj (NQobj) class is based on the QuTip Qobj but adds the machinery to use names to index modes in the Qobj instead of numbers. 

    The NQobj contains only one extra attribute, which is names, this has the same structure and size as dims of Qobj.
    names tells you which mode is called how. These names can be used to index a mode, but are most usefull to automatticaly match modes
    for math operations +,-,* between NQobj. Some of the functions of QuTiP have been rewritten in this file to allow them to use names.
    The NQobj takes the same arguments as Qobj and also the kwarg names.

    Parameters
    ----------
    Same as for QuTiP Qobj, including:
    names: str, list of str or list of two list of str
        if names is str                     --> names = [[names], [names]]
        if names is list of str             --> names = [names, names]
        if names is list of two list of str --> names = names
        Names for the modes, the shape has to match dims after the above correction.

    Attributes
    ----------
    Same as for QuTiP Qobj, including:
    names: List of the names of dimensions for keeping track of the tensor structure.

    """
    def __init__(self, *args, **kwargs):
        """
        NQobj constructor.
        """

        names = kwargs.pop('names', None)
        kind  = kwargs.pop('kind',  None)
        # If a NQobj is supplied as input and no new names are gives, use the existing ones.
        try:
            if isinstance(args[0], NQobj) and names is None:
                names = (args[0]).names
        except IndexError:
            pass

        # Initialize the Qobj without the names.
        super().__init__(*args, **kwargs)
        
        # Make sure that the format of the names is correct and add it as an attribute to the instance.
        if names is None:
            raise AttributeError('names is a compulsary attribute.')
        elif type(names) == list:
            if len(names) == 2 and type(names[0]) == list and type(names[1]) == list:
                if not all(type(i) == str for i in names[0] + names[1]):
                    raise ValueError('A name must be a string.')
                elif len(names[0]) != len(set(names[0])) or len(names[1]) != len(set(names[1])):
                    raise ValueError('Do not use duplicate names.')
                elif not (len(names[0]), len(names[1])) == self.shape_dims:
                    raise ValueError('The number of names must match the shape_dims.')
                self.names = names
            else:
                if not all(type(i) == str for i in names):
                        raise ValueError('A name must be a string.')
                elif not len(names) == len(set(names)):
                    raise ValueError('Do not use duplicate names.')
                elif not (len(names) == self.shape_dims[0] and len(names) == self.shape_dims[1]):
                    raise ValueError('The number of names must match the shape_dims.')
                self.names = [names, names]                    
        elif type(names) == str:
            if not self.shape_dims == (1, 1):
                raise ValueError('Names can only be a string if there shape_dims is (1, 1).')
            self.names = [[names], [names]]
        else:
            raise TypeError('names should be a string or 1d or 2d list ')

        if kind in ('oper', 'state'):
            self.kind = kind
        elif kind is None: #If kind is not give, try to extract it from the Qobj form
            if self.isket or self.isbra:
                self.kind = 'state'
            if self.isoper:
                if set(self.names[0]) == set(self.names[1]) and sorted(self.dims[0]) == sorted(self.dims[1]) and self.isherm:
                    raise ValueError('The kind cannot be determined automatically and should be provedid as kw ("oper" or "state")')
                else:
                    self.kind = 'oper'
        else:
            raise ValueError('kind can only be "oper", "state", None')
   
    def copy(self):
        """Create identical copy"""
        q = super().copy()
        return NQobj(q, names=deepcopy(self.names), kind=self.kind)

    def __add__(self, other):
        """
        ADDITION with NQobj on LEFT [ ex. Qobj+4 ]
        """
        if isinstance(other, NQobj):
            if not self.type == other.type:
                raise ValueError('Addition and substraction are only allowed for two NQobj of the same type.')
            elif not self.kind == other.kind:
                raise ValueError('Addition and substraction are only allowed for two NQobj of the same kind.')
            elif self.isket or self.isbra or self.isoper:
                names              = _add_find_required_names(self, other)                
                missing_self       = _find_missing_names(self.names,  names)
                missing_other      = _find_missing_names(other.names, names)
                missing_dict_self  = _find_missing_dict(missing_self, other, transpose=False)
                missing_dict_other = _find_missing_dict(missing_other, self, transpose=False)
                self               = _adding_missing_modes(self, missing_dict_self, names, kind=self.kind)
                self               = self.permute(names)
                other              = _adding_missing_modes(other, missing_dict_other, names, kind=other.kind)
                other              = other.permute(names)
                Qobj_result        = super(NQobj, self).__add__(other)
                return NQobj(Qobj_result, names=names, kind=self.kind)
            else:
                NotImplemented
        else:
            NotImplemented

    def __mul__(self, other):
        """
        MULTIPLICATION with NQobj on LEFT [ ex. NQobj*4 ]
        """
        if isinstance(other, NQobj):
            names_self, names_other = _mul_find_required_names(self, other)
            missing_self            = _find_missing_names(self.names,  names_self)
            missing_other           = _find_missing_names(other.names, names_other)
            missing_dict_self       = _find_missing_dict(missing_self, other, transpose=True)
            missing_dict_other      = _find_missing_dict(missing_other, self, transpose=True)
            self                    = _adding_missing_modes(self, missing_dict_self, names_self, kind=self.kind)
            self                    = self.permute(names_self)
            other                   = _adding_missing_modes(other, missing_dict_other, names_other, kind=other.kind)
            other                   = other.permute(names_other)
            Qobj_result = super(NQobj, self).__mul__(other)

            # Return a scalar as Qobj and not as NQobj.
            if Qobj_result.shape == (1, 1):
                return qt.Qobj(Qobj_result) 
            else:
                names = [names_self[0], names_other[1]]
                # Modes that have a size of (1, 1) have been reduced to a scalar and don't need a name anymore.     
                for name in names[0].copy():
                    if self._dim_of_name(name)[0] == 1 and other._dim_of_name(name)[1] == 1:
                        names[0].remove(name)
                        names[1].remove(name)

                if self.kind == 'oper' and other.kind == 'oper':
                    kind = 'oper'
                elif self.kind == 'state' and other.kind == 'state':
                    kind = 'oper'
                else:
                    kind = 'state'

                return NQobj(Qobj_result, names=names, kind=kind)
            
        elif isinstance(other, numbers.Number):
            return NQobj(super().__mul__(other), names=self.names, kind=self.kind)
        elif isinstance(other, qt.Qobj):
            return super().__mul__(other)
        else:
            NotImplemented
    
    def __rmul__(self, other):
        """
        MULTIPLICATION with NQobj on RIGHT [ ex. 4*Qobj ]
        """
        if isinstance(other, numbers.Number):
            return self.__mul__(other)
        elif isinstance(other, qt.Qobj):
            return other.__mul__(self)

    def __div__(self, other):
        """
        DIVISION (by numbers only)
        """
        return NQobj(super().__div__(other), names=self.names, kind=self.kind)

    def __neg__(self):        
        """
        NEGATION operation.
        """
        return NQobj(super().__neg__(), names = self.names, kind=self.kind)

    def __eq__(self, other):
        """
        EQUALITY operator.
        """
        same_Qobj = super().__eq__(other)
        same_names = self.names == other.names
        return same_Qobj and same_names

    def __pow__(self, n, m=None):
        """
        POWER operator.
        """
        return NQobj(super().__pow__(n, m=m), names = self.names, kind=self.kind)

    def __str__(self):
        return super().__str__() + '\nnames: ' + self.names.__str__() 

    def _repr_latex_(self):
        """
        Generate a LaTeX representation of the Qobj instance. Can be used for
        formatted output in ipython notebook.
        """
        s = super()._repr_latex_()
        s += r'names = {}'.format(self.names)
        s += r', kind = {}'.format(self.kind)
        return s
    
    def dag(self):
        """Adjoint operator of quantum object.
        """
        out = super().dag()
        names = [self.names[1], self.names[0]]
        return NQobj(out, names=names, kind=self.kind)
    
    def proj(self):
        """Form the projector from a given ket or bra vector."""
        return NQobj(super().proj(), names = self.names, kind='oper')

    def unit(self, *args, **kwargs):
        """Operator or state normalized to unity."""
        return NQobj(super().unit(*args, **kwargs), names = self.names, kind=self.kind)

    def ptrace(self, sel, keep=True):
        if self.dims[0] != self.dims[1]:
            ValueError('ptrace works only on a square oper')
        if self.names[0] != self.names[1]:
            ValueError('Names of both axis are not the same')
        
        if type(sel) == list:
            if all(type(i) == int for i in sel):
                pass
            elif all(type(i) == str for i in sel):
                sel = [self.names[0].index(name) for name in sel]
            else:
                raise ValueError('sel must be list of only int or str')
        else:
            raise TypeError('sel needs to be a list with int or str')

        if not keep:
            sel = [i for i in range(self.shape_dims[0]) if not i in sel]
        
        names = [name for i, name in enumerate(self.names[0]) if i in sel]
        
        return NQobj(super().ptrace(sel), names=[names, names], kind=self.kind)
    
    def permute(self, order):
        if type(order) == list and all(type(i) == str for i in order):
            order_index = []
            if self.names[0] == self.names[1]:
                for name in order:
                    order_index.append(self.names[0].index(name))
                order = order_index
            else:
                order = [order, order]
        if len(order) == 2 and \
           all(type(i) == list for i in order) and \
           all(type(i) == str for i in order[0] + order[1]):
            order_index = [[], []]
            for name in order[0]:
                order_index[0].append(self.names[0].index(name))
            for name in order[1]:
                order_index[1].append(self.names[1].index(name))
            order = order_index

        # Replicate working of permute of Qobj but with _permute2.
        q = qt.Qobj()
        q.data, q.dims = _permute2(self, order)
        q = q.tidyup() if qt.settings.auto_tidyup else q
        if type(order) == list and all(type(i) == int for i in order):
            order = [order, order]

        # Rearange the names
        names_0 = [self.names[0][i] for i in order[0]]
        names_1 = [self.names[1][i] for i in order[1]]
        names = [names_0, names_1]
        return NQobj(q, names=names, kind=self.kind)

    def rename(self, name, new_name):
        """Rename a mode called name to new_name."""
        if name == new_name:
            pass
        elif new_name in self.names[0] + self.names[1]:
            raise ValueError('You cannot use a new_name which is already used.')
        elif name not in self.names[0] + self.names[1]:
            raise ValueError('The name you want to replace is not present in the NQobj.')
        else:    
            for i in range(2):
                try:
                    self.names[i][self.names[i].index(name)] = new_name
                except ValueError:
                    pass

    def _dim_of_name(self, name):
        """Return the shape of the submatrix with name."""
        try:
            index_0 = self.names[0].index(name)
            dim_0 = self.dims[0][index_0]
        except ValueError:
            dim_0 = None
        try:
            index_1 = self.names[1].index(name)
            dim_1 = self.dims[1][index_1]
        except ValueError:
            dim_1 = None
        return (dim_0, dim_1)

    def expm(self):
        if self.names[0] == self.names[1] and self.dims[0] == self.dims[1]:
            return NQobj(super().expm(), names=self.names, kind= self.kind)
        else:
            new_self = self.expand()
            new_self.permute([new_self.names[0], new_self.names[0]])
            if new_self.names[0] == new_self.names[1] and new_self.dims[0] == new_self.dims[1]:
                return NQobj(super(NQobj, new_self).expm(), names=new_self.names, kind= new_self.kind)
            else:
                raise ValueError("For exponentiation the matrix should have square submatrixes.")
        
    @property
    def shape_dims(self): 
        shape_dims_0 = len(self.dims[0])
        shape_dims_1 = len(self.dims[1])
        return (shape_dims_0, shape_dims_1)

    def trans(self):
        return NQobj(super().trans(), names = [self.names[1], self.names[0]], kind=self.kind)

    def expand(self):
        if self.names[0] == self.names[1]:
            return self
        kind = self.kind
        required_names = self.names[0] + self.names[1]
        required_names = list(dict.fromkeys(required_names)) #Remove duplicates while keeping order (Python 3.7+)
        missing        = _find_missing_names(self.names, [required_names, required_names])
        missing_dict   = {name: self._dim_of_name(name) for name in missing[0] + missing[1]}
        names = deepcopy(self.names)
        for name, dims in missing_dict.items():
            if dims[0] is None:
                names[0].append(name)
                self = qt.tensor(self, qt.basis(dims[1]))
                self.dims[1].pop()
            elif dims[1] is None:
                names[1].append(name)
                self = qt.tensor(self, qt.basis(dims[0]).dag())
                self.dims[0].pop()
        return NQobj(self, names=names, kind=kind).permute(required_names)

def tensor(*args):
    """Perform tensor product between multiple NQobj, similar to tensor from qutip."""
    names = [[], []]
    for arg in args:
        names[0] += arg.names[0]
        names[1] += arg.names[1]
    q = qt.tensor(*args)
    kinds = np.array([q.kind for q in args])
    if not np.all(kinds == kinds[0]):
        raise AttributeError('For tensor product the kind of all NQobj should be the same.')
    out = NQobj(q, names=names, kind=kinds[0])
    return out

def ket2dm(Q):
    return NQobj(qt.ket2dm(Q), names = Q.names, kind='state')

def name(Q, names, kind=None):
    return NQobj(Q, names=names, kind=kind)

def fidelity(A, B):
    if not ((A.isket or A.isbra or A.isoper) and (B.isket or B.isbra or B.isoper)):
        raise TypeError('fidelity can only be calculated for ket, bra or oper.')
    if not set(A.names[0]) == set(A.names[1]) or not set(B.names[0]) == set(B.names[1]):
        raise TypeError('Names of colums and rows need to be the same.')
    if not set(A.names[0]) == set(B.names[0]):
        raise TypeError('fidelity needs both objects to have the same names.')
    else:
        return qt.fidelity(A, B.permute(A.names))


## Convenience functions for tracing out

def trace_out_loss_modes(Q):
    loss_modes = [x for x in Q.names[0] if 'loss' in x]
    if len(loss_modes) is not 0:
        return Q.ptrace(loss_modes, keep=False)
    else:
        return Q

def trace_out_everything_but_spins(Q):
    classic_spin_names = ['Alice', 'Bob', 'Charlie', 'alice', 'bob', 'charlie']
    spin_modes = [x for x in Q.names[0] if x in classic_spin_names]
    return Q.ptrace(spin_modes)

# To support the _permute2 function
from qutip.permute import _permute
from qutip.cy.spconvert import arr_coo2fast, cy_index_permute
import qutip.settings as settings

def _permute2(Q, order):
    """
    Similar function as _permute from qutip but this allows for permutation of non-square matrixes.
    In this case order needs to be a list of two list with the permutation for each axis. e.g. [[1,0], [1,2,0]] """
    equal_dims = Q.dims[0] == Q.dims[1]
    if type(order) == list:
        if Q.isoper:
            if equal_dims and all(type(i) == int for i in order):
                use_qutip = True
            elif len(order) == 2 and \
                 all(type(i) == list for i in order) and \
                 all(type(i) == int for i in order[0] + order[1]):  
                use_qutip = False
            else:
                raise TypeError('Order should be a list of int or a list of two list with int.')
        elif Q.isbra or Q.isket:
            if all(type(i) == int for i in order):
                use_qutip = True
            elif len(order) == 2 and \
                 all(type(i) == list for i in order) and \
                 all(type(i) == int for i in order[0] + order[1]):  
                use_qutip = False
        else:
            use_qutip = True
            # Make sure that it works if [order, order] is supplied for a different object type then oper.
            if len(order) == 2 and \
               all(type(i) == list for i in order) and \
               all(type(i) == int for i in order[0] + order[1]) and\
               order[0] == order[1]:
                order = order[0]
    if use_qutip:
        return _permute(Q, order)
    else:
        # Copy the functionality from qutip but allow for different order for rows and collums.
        Qcoo = Q.data.tocoo()
        cy_index_permute(Qcoo.row,
                         np.array(Q.dims[0], dtype=np.int32),
                         np.array(order[0], dtype=np.int32))
        cy_index_permute(Qcoo.col,
                         np.array(Q.dims[1], dtype=np.int32),
                         np.array(order[1], dtype=np.int32))

        new_dims = [[Q.dims[0][i] for i in order[0]], [Q.dims[1][i] for i in order[1]]]
        return arr_coo2fast(Qcoo.data, Qcoo.row, Qcoo.col, Qcoo.shape[0], Qcoo.shape[1]), new_dims

######################### Function to support __mul__ and __add__ functions #############################

def _mul_find_required_names(Q_left, Q_right):
    # If a mode has the form of a ket in Q_left or a bra in Q_right they don't have to be matched between the objects 
    # to perform the multiplication and are therefore not included in the required names for overlap.
    names_Q_right_for_overlap = [name for name in Q_right.names[0] if not Q_right._dim_of_name(name)[0] == 1]
    names_Q_left_for_overlap =  [name for name in  Q_left.names[1] if not  Q_left._dim_of_name(name)[1] == 1]

    # Goal is to get a list with modes that need to appear in both objects to perform the multiplication, the overlap.
    if Q_right.kind == 'state' and Q_left.kind == 'oper':
        overlap = names_Q_right_for_overlap + names_Q_left_for_overlap
    else:
        overlap = names_Q_left_for_overlap + names_Q_right_for_overlap
    overlap = list(dict.fromkeys(overlap)) #Remove duplicates while keeping order (Python 3.7+)

    # Make sure that the order of the names is matched for multiplication.
    names_Q_left  = [overlap + names for names in  Q_left.names]
    names_Q_left  = [list(dict.fromkeys(names)) for names in  names_Q_left] #Remove duplicates while keeping order (Python 3.7+)
    names_Q_right = [overlap + names for names in Q_right.names]
    names_Q_right = [list(dict.fromkeys(names)) for names in names_Q_right] #Remove duplicates while keeping order (Python 3.7+)
    return names_Q_left, names_Q_right

def _add_find_required_names(Q_left, Q_right):
    names = [Q_left.names[i] + Q_right.names[i] for i in range(2)]
    names = [list(dict.fromkeys(name_list)) for name_list in names] #Remove duplicates while keeping order (Python 3.7+)
    return names

def _find_missing_names(names, required_names):
    missing = [list(set(required_names[i]) - set(names[i])) for i in range(2)]
    return missing

def _find_missing_dict(missing_names, Q_other, transpose= False):
    missing_dict = {}
    for name in set(missing_names[0] + missing_names[1]):
        dims = list(Q_other._dim_of_name(name))
        if name not in missing_names[0]: 
            dims[0] = None
        if name not in missing_names[1]: 
            dims[1] = None
        if transpose:
            dims.reverse()
        missing_dict[name] = dims
    return missing_dict

def _adding_missing_modes(Q, dict_missing_modes, names, kind="oper"):
    modes = []
    for name, dims in dict_missing_modes.items():
        if kind == 'oper':
            assert dims[0] == dims[1], "For adding eye matrixes they need to be square"
            modes.append(NQobj(qt.qeye(dims[0]), names=name, kind='oper'))
        if kind == 'state':
            if not None in dims:
                modes.append(NQobj(qt.basis(dims[0], 0) * qt.basis(dims[1], 0).dag(), names=name, kind='state'))
            elif dims[0] is None:
                modes.append(NQobj(qt.basis(dims[1], 0).dag(),                        names=[[],[name]], kind='state'))
            elif dims[1] is None:
                modes.append(NQobj(qt.basis(dims[0], 0),                              names=name, kind='state'))
    return tensor(Q, *modes)