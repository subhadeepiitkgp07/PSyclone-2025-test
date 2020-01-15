# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2019-2020, Science and Technology Facilities Council.
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
# Authors S. Siso, STFC Daresbury Lab
# -----------------------------------------------------------------------------

''' Performs py.test tests on the Operation PSyIR node. '''

from __future__ import absolute_import
import pytest
from psyclone.psyir.nodes import UnaryOperation, BinaryOperation, \
    NaryOperation, Literal, Reference
from psyclone.psyir.symbols import DataType
from psyclone.psyGen import GenerationError
from psyclone.psyir.backend.fortran import FortranWriter
from psyclone.tests.utilities import check_links

# Test BinaryOperation class
def test_binaryoperation_initialization():
    ''' Check the initialization method of the BinaryOperation class works
    as expected.'''

    with pytest.raises(TypeError) as err:
        _ = BinaryOperation("not an operator")
    assert "BinaryOperation operator argument must be of type " \
           "BinaryOperation.Operator but found" in str(err.value)
    bop = BinaryOperation(BinaryOperation.Operator.ADD)
    assert bop._operator is BinaryOperation.Operator.ADD


def test_binaryoperation_operator():
    '''Test that the operator property returns the binaryoperator in the
    binaryoperation.

    '''
    binary_operation = BinaryOperation(BinaryOperation.Operator.ADD)
    assert binary_operation.operator == BinaryOperation.Operator.ADD


def test_binaryoperation_node_str():
    ''' Check the node_str method of the Binary Operation class.'''
    from psyclone.psyir.nodes.node import colored, SCHEDULE_COLOUR_MAP
    binary_operation = BinaryOperation(BinaryOperation.Operator.ADD)
    op1 = Literal("1", DataType.INTEGER, parent=binary_operation)
    op2 = Literal("1", DataType.INTEGER, parent=binary_operation)
    binary_operation.addchild(op1)
    binary_operation.addchild(op2)
    coloredtext = colored("BinaryOperation",
                          SCHEDULE_COLOUR_MAP["Operation"])
    assert coloredtext+"[operator:'ADD']" in binary_operation.node_str()


def test_binaryoperation_can_be_printed():
    '''Test that a Binary Operation instance can always be printed (i.e. is
    initialised fully)'''
    binary_operation = BinaryOperation(BinaryOperation.Operator.ADD)
    assert "BinaryOperation[operator:'ADD']" in str(binary_operation)
    op1 = Literal("1", DataType.INTEGER, parent=binary_operation)
    op2 = Literal("2", DataType.INTEGER, parent=binary_operation)
    binary_operation.addchild(op1)
    binary_operation.addchild(op2)
    # Check the node children are also printed
    assert "Literal[value:'1', DataType.INTEGER]\n" in str(binary_operation)
    assert "Literal[value:'2', DataType.INTEGER]" in str(binary_operation)


def test_binaryoperation_create():
    '''Test that the create method in the BinaryOperation class correctly
    creates a BinaryOperation instance.

    '''
    lhs = Reference("tmp1")
    rhs = Reference("tmp2")
    oper = BinaryOperation.Operator.ADD
    binaryoperation = BinaryOperation.create(oper, lhs, rhs)
    check_links(binaryoperation, [lhs, rhs])
    result = FortranWriter().binaryoperation_node(binaryoperation)
    assert result == "tmp1 + tmp2"


def test_binaryoperation_create_invalid():
    '''Test that the create method in a BinaryOperation class raises the
    expected exception if the provided input is invalid.

    '''
    ref1 = Reference("tmp1")
    ref2 = Reference("tmp2")
    add = BinaryOperation.Operator.ADD

    # oper not a BinaryOperation.Operator.
    with pytest.raises(GenerationError) as excinfo:
        _ = BinaryOperation.create("invalid", ref1, ref2)
    assert ("oper argument in create method of BinaryOperation class should "
            "be a PSyIR BinaryOperation Operator but found 'str'."
            in str(excinfo.value))

    # lhs not a Node.
    with pytest.raises(GenerationError) as excinfo:
        _ = BinaryOperation.create(add, "invalid", ref2)
    assert ("lhs argument in create method of BinaryOperation class should "
            "be a PSyIR Node but found 'str'.") in str(excinfo.value)

    # rhs not a Node.
    with pytest.raises(GenerationError) as excinfo:
        _ = BinaryOperation.create(add, ref1, "invalid")
    assert ("rhs argument in create method of BinaryOperation class should "
            "be a PSyIR Node but found 'str'.") in str(excinfo.value)


# Test UnaryOperation class
def test_unaryoperation_initialization():
    ''' Check the initialization method of the UnaryOperation class works
    as expected.'''

    with pytest.raises(TypeError) as err:
        _ = UnaryOperation("not an operator")
    assert "UnaryOperation operator argument must be of type " \
           "UnaryOperation.Operator but found" in str(err.value)
    uop = UnaryOperation(UnaryOperation.Operator.MINUS)
    assert uop._operator is UnaryOperation.Operator.MINUS


def test_unaryoperation_operator():
    '''Test that the operator property returns the unaryoperator in the
    unaryoperation.

    '''
    unary_operation = UnaryOperation(UnaryOperation.Operator.MINUS)
    assert unary_operation.operator == UnaryOperation.Operator.MINUS


def test_unaryoperation_node_str():
    ''' Check the view method of the UnaryOperation class.'''
    from psyclone.psyir.nodes.node import colored, SCHEDULE_COLOUR_MAP
    unary_operation = UnaryOperation(UnaryOperation.Operator.MINUS)
    ref1 = Reference("a", parent=unary_operation)
    unary_operation.addchild(ref1)
    coloredtext = colored("UnaryOperation",
                          SCHEDULE_COLOUR_MAP["Operation"])
    assert coloredtext+"[operator:'MINUS']" in unary_operation.node_str()


def test_unaryoperation_can_be_printed():
    '''Test that a UnaryOperation instance can always be printed (i.e. is
    initialised fully)'''
    unary_operation = UnaryOperation(UnaryOperation.Operator.MINUS)
    assert "UnaryOperation[operator:'MINUS']" in str(unary_operation)
    op1 = Literal("1", DataType.INTEGER, parent=unary_operation)
    unary_operation.addchild(op1)
    # Check the node children are also printed
    assert "Literal[value:'1', DataType.INTEGER]" in str(unary_operation)


def test_unaryoperation_create():
    '''Test that the create method in the UnaryOperation class correctly
    creates a UnaryOperation instance.

    '''
    child = Reference("tmp")
    oper = UnaryOperation.Operator.SIN
    unaryoperation = UnaryOperation.create(oper, child)
    check_links(unaryoperation, [child])
    result = FortranWriter().unaryoperation_node(unaryoperation)
    assert result == "SIN(tmp)"


def test_unaryoperation_create_invalid():
    '''Test that the create method in a UnaryOperation class raises the
    expected exception if the provided input is invalid.

    '''
    # oper not a UnaryOperator.Operator.
    with pytest.raises(GenerationError) as excinfo:
        _ = UnaryOperation.create("invalid", Reference("tmp"))
    assert ("oper argument in create method of UnaryOperation class should "
            "be a PSyIR UnaryOperation Operator but found 'str'."
            in str(excinfo.value))

    # child not a Node.
    with pytest.raises(GenerationError) as excinfo:
        _ = UnaryOperation.create(UnaryOperation.Operator.SIN, "invalid")
    assert ("child argument in create method of UnaryOperation class should "
            "be a PSyIR Node but found 'str'.") in str(excinfo.value)


def test_naryoperation_node_str():
    ''' Check the node_str method of the Nary Operation class.'''
    from psyclone.psyir.nodes.node import colored, SCHEDULE_COLOUR_MAP
    nary_operation = NaryOperation(NaryOperation.Operator.MAX)
    nary_operation.addchild(Literal("1", DataType.INTEGER,
                                    parent=nary_operation))
    nary_operation.addchild(Literal("1", DataType.INTEGER,
                                    parent=nary_operation))
    nary_operation.addchild(Literal("1", DataType.INTEGER,
                                    parent=nary_operation))

    coloredtext = colored("NaryOperation",
                          SCHEDULE_COLOUR_MAP["Operation"])
    assert coloredtext+"[operator:'MAX']" in nary_operation.node_str()


def test_naryoperation_can_be_printed():
    '''Test that an Nary Operation instance can always be printed (i.e. is
    initialised fully)'''
    nary_operation = NaryOperation(NaryOperation.Operator.MAX)
    assert "NaryOperation[operator:'MAX']" in str(nary_operation)
    nary_operation.addchild(Literal("1", DataType.INTEGER,
                                    parent=nary_operation))
    nary_operation.addchild(Literal("2", DataType.INTEGER,
                                    parent=nary_operation))
    nary_operation.addchild(Literal("3", DataType.INTEGER,
                                    parent=nary_operation))
    # Check the node children are also printed
    assert "Literal[value:'1', DataType.INTEGER]\n" in str(nary_operation)
    assert "Literal[value:'2', DataType.INTEGER]\n" in str(nary_operation)
    assert "Literal[value:'3', DataType.INTEGER]" in str(nary_operation)


def test_naryoperation_create():
    '''Test that the create method in the NaryOperation class correctly
    creates an NaryOperation instance.

    '''
    children = [Reference("tmp1"), Reference("tmp2"), Reference("tmp3")]
    oper = NaryOperation.Operator.MAX
    naryoperation = NaryOperation.create(oper, children)
    check_links(naryoperation, children)
    result = FortranWriter().naryoperation_node(naryoperation)
    assert result == "MAX(tmp1, tmp2, tmp3)"


def test_naryoperation_create_invalid():
    '''Test that the create method in an NaryOperation class raises the
    expected exception if the provided input is invalid.

    '''
    # oper not an NaryOperation.Operator
    with pytest.raises(GenerationError) as excinfo:
        _ = NaryOperation.create("invalid", [])
    assert ("oper argument in create method of NaryOperation class should "
            "be a PSyIR NaryOperation Operator but found 'str'."
            in str(excinfo.value))

    # children not a list
    with pytest.raises(GenerationError) as excinfo:
        _ = NaryOperation.create(NaryOperation.Operator.SUM, "invalid")
    assert ("children argument in create method of NaryOperation class should "
            "be a list but found 'str'." in str(excinfo.value))

    # contents of children list are not Node
    with pytest.raises(GenerationError) as excinfo:
        _ = NaryOperation.create(NaryOperation.Operator.SUM,
                                 [Reference("tmp1"), "invalid"])
    assert (
        "child of children argument in create method of NaryOperation class "
        "should be a PSyIR Node but found 'str'." in str(excinfo.value))
