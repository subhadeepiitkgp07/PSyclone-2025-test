# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2021-2023, Science and Technology Facilities Council
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
# -----------------------------------------------------------------------------
# Author: J. Henrichs, Bureau of Meteorology
# Modified: S. Siso, STFC Daresbury Lab


'''PSyIR backend to create expressions that are handled by sympy.
'''

from sympy import Function, Symbol
from sympy.parsing.sympy_parser import parse_expr

from psyclone.psyir.backend.fortran import FortranWriter
from psyclone.psyir.backend.visitor import VisitorError
from psyclone.psyir.nodes import DataNode, Range, Reference, IntrinsicCall, \
    Schedule
from psyclone.psyir.symbols import ArrayType, ScalarType, SymbolTable


class SymPyWriter(FortranWriter):
    '''Implements a PSyIR-to-sympy writer, which is used to create a
    representation of the PSyIR tree that can be understood by SymPy. Most
    Fortran expressions work as expected without modification. This class
    implements special handling for constants (which can have a precision
    attached, e.g. 2_4) and some intrinsic functions (e.g. ``MAX``, which SymPy
    expects to be ``Max``). Array accesses are converted into functions (while
    SymPy supports indexed expression, they cannot be used as expected when
    solving, SymPy does not solve component-wise - ``M[x]-M[1]`` would not
    result in ``x=1``, while it does for SymPy unknown functions).
    Array expressions are supported by the writer: it will convert any array
    expression like ``a(i:j:k)`` by using three arguments: ``a(i, j, k)``.
    Then simple array accesses like ``b(i,j)`` are converted to
    ``b(i,i,1,j,j,1)``. Similarly, if ``a`` is known to be an array, then the
    writer will use ``a(sympy_lower,sympy_upper,1)``. This makes sure all SymPy
    unknown functions that represent an array use the same number of
    arguments.

    The simple use case of converting a (list of) PSyIR expressions to SymPy
    expressions is as follows::

        symp_expr_list = SymPyWriter(exp1, exp2, ...)

    If additional functionality is required (access to the type map or
    to convert a potentially modified SymPy expression back to PSyIR), an
    instance of SymPy writer must be created::

        writer = SymPyWriter()
        symp_expr_list = writer([exp1, exp2, ...])

    It additionally supports accesses to structure types. A full description
    can be found in the manual:
    https://psyclone-dev.readthedocs.io/en/latest/sympy.html#sympy

    '''
    # This option will disable the lowering of abstract nodes into language
    # level nodes, and as a consequence the backend does not need to deep-copy
    # the tree and is much faster to execute.
    # Be careful not to modify anything from the input tree when this option
    # is set to True as the modifications will persist after the Writer!
    _DISABLE_LOWERING = True

    def __init__(self):
        super().__init__()

        # The symbol table is used to create unique names for structure
        # members that are being accessed (these need to be defined as
        # SymPy functions or symbols, which could clash with other
        # references in the expression).
        self._symbol_table = None

        # The writer will use special names in array expressions to indicate
        # the lower and upper bound (e.g. ``a(::)`` becomes
        # ``a(sympy_lower, sympy_upper, 1)``). The symbol table will be used
        # to resolve a potential name clash with a user variable.
        self._lower_bound = "sympy_lower"
        self._upper_bound = "sympy_upper"

        self._sympy_type_map = {}
        self._intrinsic = set()
        self._intrinsic_to_str = {}

        # Create the mapping of intrinsics to the name SymPy expects.
        for intr, intr_str in [(IntrinsicCall.Intrinsic.MAX, "Max"),
                               (IntrinsicCall.Intrinsic.MIN, "Min"),
                               (IntrinsicCall.Intrinsic.FLOOR, "floor"),
                               (IntrinsicCall.Intrinsic.TRANSPOSE,
                                "transpose"),
                               (IntrinsicCall.Intrinsic.MOD, "Mod"),
                               # exp is needed for a test case only, in
                               # general the maths functions can just be
                               # handled as unknown sympy functions.
                               (IntrinsicCall.Intrinsic.EXP, "exp"),
                               ]:
            self._intrinsic.add(intr_str)
            self._intrinsic_to_str[intr] = intr_str

    # -------------------------------------------------------------------------
    def __new__(cls, *expressions):
        '''This function allows the SymPy writer to be used in two
        different ways: if only the SymPy expression of the PSyIR expressions
        are required, it can be called as::

            sympy_expressions = SymPyWriter(exp1, exp2, ...)

        But if additional information is needed (e.g. the SymPy type map, or
        to convert a SymPy expression back to PSyIR), an instance of the
        SymPyWriter must be kept, e.g.::

            writer = SymPyWriter()
            sympy_expressions = writer([exp1, exp2, ...])
            writer.type_map

        :param expressions: a (potentially empty) tuple of PSyIR nodes
            to be converted to SymPy expressions.
        :type expressions: Tuple[:py:class:`psyclone.psyir.nodes.Node`]

        :returns: either an instance of SymPyWriter, if no parameter is
            specified, or a list of SymPy expressions.
        :rtype: Union[:py:class:`psyclone.psyir.backend.SymPyWriter`,
                      List[:py:class:`sympy.core.basic.Basic`]]

        '''
        if expressions:
            # If we have parameters, create an instance of the writer
            # and use it to convert the expressions:
            writer = SymPyWriter()
            return writer(expressions)

        # No parameter, just create an instance and return it:
        return super().__new__(cls)

    # -------------------------------------------------------------------------
    def __getitem__(self, _):
        '''This function is only here to trick pylint into thinking that
        the object returned from ``__new__`` is subscriptable, meaning that
        code like:
        ``out = SymPyWriter(exp1, exp2); out[1]`` does not trigger
        a pylint warning about unsubscriptable-object.
        '''
        raise NotImplementedError("__getitem__ for a SymPyWriter should "
                                  "never be called.")

    # -------------------------------------------------------------------------
    def _create_type_map(self, list_of_expressions):
        '''This function creates a dictionary mapping each Reference in any
        of the expressions to either a SymPy Function (if the reference
        is an array reference) or a Symbol (if the reference is not an
        array reference). It defines a new SymPy function for each array,
        which has a special write method implemented that automatically
        converts array indices back by combining each three arguments into
        one expression (i. e. ``a(1,9,2)`` would become ``a(1:9:2)``).

        A new symbol table is created any time this function is called, so
        it is important to provide all expressions at once for the symbol
        table to avoid name clashes in any expression.

        :param list_of_expressions: the list of expressions from which all
            references are taken and added to a symbol table to avoid
            renaming any symbols (so that only member names will be renamed).
        :type list_of_expressions: List[:py:class:`psyclone.psyir.nodes.Node`]

        '''
        # Avoid circular dependency
        # pylint: disable=import-outside-toplevel
        from psyclone.psyir.frontend.sympy_reader import SymPyReader

        # Create a new symbol table, so previous symbol will not affect this
        # new conversion (i.e. this avoids name clashes with a previous
        # conversion).
        self._symbol_table = SymbolTable()

        # Find each reference in each of the expression, and declare this name
        # as either a SymPy Symbol (scalar reference), or a SymPy Function
        # (an array).
        for expr in list_of_expressions:
            for ref in expr.walk(Reference):
                name = ref.name
                if name in self._symbol_table:
                    # The name has already been declared, ignore it now
                    continue

                # Add the new name to the symbol table to mark it
                # as done
                self._symbol_table.find_or_create(name)

                # Test if an array or an array expression is used:
                if not ref.is_array:
                    # A simple scalar, create a SymPy symbol
                    self._sympy_type_map[name] = Symbol(name)
                    continue

                # Now a new Fortran array is used. Create a new function
                # instance, and overwrite how this function is converted back
                # into a string by defining the ``_sympystr`` attribute,
                # which points to a function that controls how this object
                # is converted into a string. Use the ``print_fortran_array``
                # function from the SymPyReader for this. Note that we cannot
                # create a derived class based on ``Function`` and define
                # this function there: SymPy tests internally if the type is a
                # Function (not if it is an instance), therefore, SymPy's
                # behaviour would change if we used a derived class.
                array_func = Function(name)
                # pylint: disable=protected-access
                array_func._sympystr = SymPyReader.print_fortran_array
                # pylint: enable=protected-access
                self._sympy_type_map[name] = array_func

        # Now all symbols have been added to the symbol table, create
        # unique names for the lower- and upper-bounds using special tags:
        self._lower_bound = \
            self._symbol_table.new_symbol("sympy_lower",
                                          tag="sympy!lower_bound").name
        self._upper_bound = \
            self._symbol_table.new_symbol("sympy_upper",
                                          tag="sympy!upper_bound").name

    # -------------------------------------------------------------------------
    @property
    def lower_bound(self):
        ''':returns: the name to be used for an unspecified lower bound.
        :rtype: str

        '''
        return self._lower_bound

    # -------------------------------------------------------------------------
    @property
    def upper_bound(self):
        ''':returns: the name to be used for an unspecified upper bound.
        :rtype: str

        '''
        return self._upper_bound

    # -------------------------------------------------------------------------
    @property
    def type_map(self):
        ''':returns: the mapping of names to SymPy symbols or functions.
        :rtype: Dict[str, Union[:py:class:`sympy.core.symbol.Symbol`,
                                :py:class:`sympy.core.function.Function`]]

        '''
        return self._sympy_type_map

    # -------------------------------------------------------------------------
    def _to_str(self, list_of_expressions):
        '''Converts PSyIR expressions to strings. It will replace Fortran-
        specific expressions with code that can be parsed by SymPy. The
        argument can either be a single element (in which case a single string
        is returned) or a list/tuple, in which case a list is returned.

        :param list_of_expressions: the list of expressions which are to be
            converted into SymPy-parsable strings.
        :type list_of_expressions: Union[:py:class:`psyclone.psyir.nodes.Node`,
            List[:py:class:`psyclone.psyir.nodes.Node`]]

        :returns: the converted strings(s).
        :rtype: Union[str, List[str]]

        '''
        is_list = isinstance(list_of_expressions, (tuple, list))
        if not is_list:
            list_of_expressions = [list_of_expressions]

        # Create the type map in `self._sympy_type_map`, which is required
        # when converting these strings to SymPy expressions
        self._create_type_map(list_of_expressions)

        expression_str_list = []
        for expr in list_of_expressions:
            expression_str_list.append(super().__call__(expr))

        # If the argument was a single expression, only return a single
        # expression, otherwise return a list
        if not is_list:
            return expression_str_list[0]
        return expression_str_list

    # -------------------------------------------------------------------------
    def __call__(self, list_of_expressions):
        '''
        This function takes a list of PSyIR expressions, and converts
        them all into Sympy expressions using the SymPy parser.
        It takes care of all Fortran specific conversion required (e.g.
        constants with kind specification, ...), including the renaming of
        member accesses, as described in
        https://psyclone-dev.readthedocs.io/en/latest/sympy.html#sympy

        :param list_of_expressions: the list of expressions which are to be
            converted into SymPy-parsable strings.
        :type list_of_expressions: list of
            :py:class:`psyclone.psyir.nodes.Node`

        :returns: a 2-tuple consisting of the the converted PSyIR
            expressions, followed by a dictionary mapping the symbol names
            to SymPy Symbols.
        :rtype: Union[:py:class:`sympy.core.basic.Basic`,
                      List[:py:class:`sympy.core.basic.Basic`]]

        :raises VisitorError: if an invalid SymPy expression is found.

        '''
        is_list = isinstance(list_of_expressions, (tuple, list))
        if not is_list:
            list_of_expressions = [list_of_expressions]
        expression_str_list = self._to_str(list_of_expressions)

        result = []
        for expr in expression_str_list:
            try:
                result.append(parse_expr(expr, self.type_map))
            except SyntaxError as err:
                raise VisitorError(f"Invalid SymPy expression: '{expr}'.") \
                    from err

        if is_list:
            return result
        # We had no list initially, so only convert the one and only
        # list member
        return result[0]

    # -------------------------------------------------------------------------
    def member_node(self, node):
        '''In SymPy an access to a member ``b`` of a structure ``a``
        (i.e. ``a%b`` in Fortran) is handled as the ``MOD`` function
        ``MOD(a, b)``. We must therefore make sure that a member
        access is unique (e.g. ``b`` could already be a scalar variable).
        This is done by creating a new name, which replaces the ``%``
        with an ``_``. So ``a%b`` becomes ``MOD(a, a_b)``. This makes it easier
        to see where the function names come from.
        Additionally, we still need to avoid a name clash, e.g. there
        could already be a variable ``a_b``. This is done by using a symbol
        table, which was prefilled with all references (``a`` in the example
        above) in the constructor. We use the string containing the ``%`` as
        a unique tag and get a new, unique symbol from the symbol table
        based on the new name using ``_``. For example, the access to member
        ``b`` in ``a(i)%b`` would result in a new symbol with tag ``a%b`` and a
        name like ``a_b`, `a_b_1``, ...

        :param node: a Member PSyIR node.
        :type node: :py:class:`psyclone.psyir.nodes.Member`

        :returns: the SymPy representation of this member access.
        :rtype: str

        '''
        # We need to find the parent reference in order to make a new
        # name (a%b%c --> a_b_c). Collect the names of members and the
        # symbol in a list.
        parent = node
        name_list = [node.name]
        while not isinstance(parent, Reference):
            parent = parent.parent
            name_list.append(parent.name)
        name_list.reverse()

        # The root name uses _, the tag uses % (which are guaranteed
        # to be unique, the root_name might clash with a user defined
        # variable otherwise).
        root_name = "_".join(name_list)
        sig_name = "%".join(name_list)
        new_sym = self._symbol_table.find_or_create_tag(tag=sig_name,
                                                        root_name=root_name)
        new_name = new_sym.name
        if new_name not in self._sympy_type_map:
            if node.is_array:
                self._sympy_type_map[new_name] = Function(new_name)
            else:
                self._sympy_type_map[new_name] = Symbol(new_name)

        # Now get the original string that this node produces:
        original_name = super().member_node(node)

        # And replace the `node.name` (which must be at the beginning since
        # it is a member) with the new name from the symbol table:
        return new_name + original_name[len(node.name):]

    # -------------------------------------------------------------------------
    def literal_node(self, node):
        '''This method is called when a Literal instance is found in the PSyIR
        tree. For SymPy we need to handle booleans (which are expected to
        be capitalised: True). Real values work by just ignoring any precision
        information (e.g. 2_4, 3.1_wp). Character constants are not supported
        and will raise an exception.

        :param node: a Literal PSyIR node.
        :type node: :py:class:`psyclone.psyir.nodes.Literal`

        :returns: the SymPy representation for the literal.
        :rtype: str

        :raises TypeError: if a character constant is found, which
            is not supported with SymPy.

        '''
        if node.datatype.intrinsic == ScalarType.Intrinsic.BOOLEAN:
            # Booleans need to be converted to SymPy format
            return node.value.capitalize()

        if node.datatype.intrinsic == ScalarType.Intrinsic.CHARACTER:
            raise TypeError(f"SymPy cannot handle strings "
                            f"like '{node.value}'.")
        # All real (single, double precision) and integer work by just
        # using the node value. Single and double precision both use
        # 'e' as specification, which SymPy accepts, and precision
        # information can be ignored.
        return node.value

    def intrinsiccall_node(self, node):
        # Sympy does not support argument names, remove them for now
        if any(node.argument_names):
            # FIXME: Do this inside Call?
            # TODO: This is not totally right without canonical intrinsic
            # positions?
            for idx in range(len(node.argument_names)):
                node._argument_names[idx] = (node._argument_names[idx][0], None)
            # raise VisitorError(
            #     f"Named arguments are not supported by SymPy but found: "
            #     f"'{node.debug_string()}'.")
        try:
            name = self._intrinsic_to_str[node.intrinsic]
            args = self._gen_arguments(node)
            if not node.parent or isinstance(node.parent, Schedule):
                return f"{self._nindent}call {name}({args})\n"
            else:
                return f"{self._nindent}{name}({args})"
        except KeyError:
            return super().call_node(node)

    # -------------------------------------------------------------------------
    def is_intrinsic(self, operator):
        '''Determine whether the supplied operator is an intrinsic
        function (i.e. needs to be used as `f(a,b)`) or not (i.e. used
        as `a + b`). This tests for known SymPy names of these functions
        (e.g. Max), and otherwise calls the function in the base class.

        :param str operator: the supplied operator.

        :returns: true if the supplied operator is an
            intrinsic and false otherwise.

        '''
        if operator in self._intrinsic:
            return True

        return super().is_intrinsic(operator)

    # -------------------------------------------------------------------------
    def reference_node(self, node):
        '''This method is called when a Reference instance is found in the
        PSyIR tree. It handles the case that this normal reference might
        be an array expression, which in the SymPy writer needs to have
        indices added explicitly: it basically converts the array expression
        ``a`` to ``a(sympy_lower, sympy_upper, 1)``.

        :param node: a Reference PSyIR node.
        :type node: :py:class:`psyclone.psyir.nodes.Reference`

        :returns: the text representation of this reference.
        :rtype: str

        '''
        if not node.is_array:
            # This reference is not an array, handle its conversion to
            # string in the FortranWriter base class
            return super().reference_node(node)

        # Now this must be an array expression without parenthesis. Add
        # the triple-array indices to represent `lower:upper:1` for each
        # dimension:
        shape = node.symbol.shape
        result = [f"{self.lower_bound},"
                  f"{self.upper_bound},1"]*len(shape)

        return (f"{node.name}{self.array_parenthesis[0]}"
                f"{','.join(result)}{self.array_parenthesis[1]}")

    # ------------------------------------------------------------------------
    def gen_indices(self, indices, var_name=None):
        '''Given a list of PSyIR nodes representing the dimensions of an
        array, return a list of strings representing those array dimensions.
        This is used both for array references and array declarations. Note
        that 'indices' can also be a shape in case of Fortran. The
        implementation here overwrites the one in the base class to convert
        each array index into three parameters to support array expressions.

        :param indices: list of PSyIR nodes.
        :type indices: List[:py:class:`psyclone.psyir.symbols.Node`]
        :param str var_name: name of the variable for which the dimensions
            are created. Not used in this implementation.

        :returns: the Fortran representation of the dimensions.
        :rtype: List[str]

        :raises NotImplementedError: if the format of the dimension is not
            supported.

        '''
        dims = []
        for index in indices:
            if isinstance(index, DataNode):
                # literal constant, symbol reference, or computed
                # dimension
                expression = self._visit(index)
                dims.extend([expression, expression, "1"])
            elif isinstance(index, Range):
                # literal constant, symbol reference, or computed
                # dimension
                expression = self._visit(index)
                dims.append(expression)
            elif isinstance(index, ArrayType.ArrayBounds):
                # Lower and upper bounds of an array declaration specified
                # by literal constant, symbol reference, or computed dimension
                lower_expression = self._visit(index.lower)
                upper_expression = self._visit(index.upper)
                dims.extend([lower_expression, upper_expression, "1"])
            elif isinstance(index, ArrayType.Extent):
                # unknown extent
                dims.extend([self.lower_bound, self.upper_bound, "1"])
            else:
                raise NotImplementedError(
                    f"unsupported gen_indices index '{index}'")
        return dims

    # -------------------------------------------------------------------------
    def range_node(self, node):
        '''This method is called when a Range instance is found in the PSyIR
        tree. This implementation converts a range into three parameters
        for the corresponding SymPy function.

        :param node: a Range PSyIR node.
        :type node: :py:class:`psyclone.psyir.nodes.Range`

        :returns: the Fortran code as a string.
        :rtype: str

        '''
        if node.parent and node.parent.is_lower_bound(
                node.parent.indices.index(node)):
            # The range starts for the first element in this
            # dimension, so use the generic name for lower bound:
            start = self.lower_bound
        else:
            start = self._visit(node.start)

        if node.parent and node.parent.is_upper_bound(
                node.parent.indices.index(node)):
            # The range ends with the last element in this
            # dimension, so use the generic name for the upper bound:
            stop = self.upper_bound
        else:
            stop = self._visit(node.stop)
        result = f"{start},{stop}"

        step = self._visit(node.step)
        result += f",{step}"

        return result
