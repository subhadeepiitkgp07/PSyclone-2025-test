# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2021-2024, Science and Technology Facilities Council.
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
# Author Julien Remy, Université Grenoble Alpes & Inria

"""Performs pytest tests on the support for comments in the fparser2
PSyIR front-end"""

import pytest

from psyclone.psyir.frontend.fortran import FortranReader
from psyclone.psyir.nodes import (Container, Routine, Assignment,
                                  Loop, IfBlock, Call)
from psyclone.psyir.nodes.commentable_mixin import CommentableMixin
from psyclone.psyir.symbols import DataTypeSymbol, StructureType

from psyclone.psyir.backend.fortran import FortranWriter

# Test code
CODE = """
! Comment on module 'test_mod'
! and second line
module test_mod
  implicit none
  ! Comment on derived type 'my_type' SHOULD BE LOST
  type :: my_type
    ! Comment on component 'i'
    ! and second line
    integer :: i
    ! Comment on component 'j'
    integer :: j
  end type my_type
contains
  ! Comment on a subroutine
  subroutine test_sub()
    ! Comment on variable 'a'
    ! and second line
    integer :: a
    ! Comment on variable 'i'
    integer :: i
    ! Comment on variable 'j'
    integer :: j
    ! Comment on assignment 'a = 1'
    ! and second line
    a = 1
    ! Comment on call 'call test_sub()'
    call test_sub()
    ! Comment on if block 'if (a == 1) then'
    if (a == 1) then
      ! Comment on assignment 'a = 2'
      a = 2
    ! Comment on elseif block 'elseif (a == 2) then' SHOULD BE LOST
    elseif (a == 2) then
      ! Comment on assignment 'a = 3'
      a = 3
    ! Comment on else block 'else' SHOULD BE LOST
    else
      ! Comment on assignment 'a = 4'
      a = 4
    ! Comment on 'end if' SHOULD BE LOST
    end if
    ! Comment on loop 'do i = 1, 10'
    do i = 1, 10
      ! Comment on assignment 'a = 5'
      a = 5
      ! Comment on loop 'do j = 1, 10'
        do j = 1, 10
          ! Comment on assignment 'a = 6'
          a = 6
        end do
    end do
  end subroutine test_sub
end module test_mod
"""


def test_no_comments():
    """Test that the FortranReader is without comments by default"""
    reader = FortranReader()
    psyir = reader.psyir_from_source(CODE)

    module = psyir.children[0]
    assert isinstance(module, Container)
    assert module.name == "test_mod"
    assert module.preceding_comment == ""

    my_type_sym = module.symbol_table.lookup("my_type")
    assert isinstance(my_type_sym, DataTypeSymbol)
    assert my_type_sym.preceding_comment == ""

    assert isinstance(my_type_sym.datatype, StructureType)
    for component in my_type_sym.datatype.components.values():
        assert component.preceding_comment == ""

    routine = module.walk(Routine)[0]
    assert routine.name == "test_sub"
    assert routine.preceding_comment == ""
    for symbol in routine.symbol_table.symbols:
        assert symbol.preceding_comment == ""
    commentable_nodes = routine.walk(CommentableMixin)
    assert len(commentable_nodes) != 0
    for node in commentable_nodes:
        assert node.preceding_comment == ""


def test_comments():
    """Test that the FortranReader is able to read comments"""
    reader = FortranReader()
    psyir = reader.psyir_from_source(CODE, ignore_comments=False)

    module = psyir.children[0]
    assert module.preceding_comment == "Comment on module 'test_mod'\nand second line"

    # TODO: add support for comments on derived types.
    my_type_sym = module.symbol_table.lookup("my_type")
    assert my_type_sym.preceding_comment == ""

    assert isinstance(my_type_sym.datatype, StructureType)
    for i, component in enumerate(my_type_sym.datatype.components.values()):
        if i == 0:
            assert component.preceding_comment == "Comment on component 'i'\nand second line"
        else:
            assert component.preceding_comment == "Comment on component 'j'"

    routine = module.walk(Routine)[0]
    assert routine.preceding_comment == "Comment on a subroutine"

    for i, symbol in enumerate(routine.symbol_table.symbols):
        if i == 0:
            assert symbol.preceding_comment == "Comment on variable 'a'\nand second line"
        else:
            assert symbol.preceding_comment == f"Comment on variable '{symbol.name}'"

    for i, assignment in enumerate(routine.walk(Assignment)):
        if i == 0:
            assert assignment.preceding_comment == "Comment on assignment 'a = 1'\nand second line"
        else:
            assert assignment.preceding_comment == f"Comment on assignment 'a = {i+1}'"

    call = routine.walk(Call)[0]
    assert call.preceding_comment == "Comment on call 'call test_sub()'"

    ifblock = routine.walk(IfBlock)[0]
    assert ifblock.preceding_comment == "Comment on if block 'if (a == 1) then'"

    loops = routine.walk(Loop)
    loop_i = loops[0]
    # OMP directives should be ignored
    assert loop_i.preceding_comment == "Comment on loop 'do i = 1, 10'"

    loop_j = loops[1]
    assert loop_j.preceding_comment == "Comment on loop 'do j = 1, 10'"


EXPECTED_WITH_COMMENTS = """! Comment on module 'test_mod'
! and second line
module test_mod
  implicit none
  type, public :: my_type
    ! Comment on component 'i'
    ! and second line
    integer, public :: i
    ! Comment on component 'j'
    integer, public :: j
  end type my_type
  public

  contains
  ! Comment on a subroutine
  subroutine test_sub()
    ! Comment on variable 'a'
    ! and second line
    integer :: a
    ! Comment on variable 'i'
    integer :: i
    ! Comment on variable 'j'
    integer :: j

    ! Comment on assignment 'a = 1'
    ! and second line
    a = 1
    ! Comment on call 'call test_sub()'
    call test_sub()
    ! Comment on if block 'if (a == 1) then'
    if (a == 1) then
      ! Comment on assignment 'a = 2'
      a = 2
    else
      if (a == 2) then
        ! Comment on assignment 'a = 3'
        a = 3
      else
        ! Comment on assignment 'a = 4'
        a = 4
      end if
    end if
    ! Comment on loop 'do i = 1, 10'
    do i = 1, 10, 1
      ! Comment on assignment 'a = 5'
      a = 5
      ! Comment on loop 'do j = 1, 10'
      do j = 1, 10, 1
        ! Comment on assignment 'a = 6'
        a = 6
      enddo
    enddo

  end subroutine test_sub

end module test_mod
"""


def test_write_comments():
    """Test that the comments are written back to the code"""
    reader = FortranReader()
    writer = FortranWriter()
    psyir = reader.psyir_from_source(CODE, ignore_comments=False)
    generated_code = writer(psyir)
    assert generated_code == EXPECTED_WITH_COMMENTS


CODE_WITH_DIRECTIVE = """
subroutine test_sub()
  integer :: a
  integer :: i
  ! Comment on loop 'do i = 1, 10'
  !$omp parallel do
  do i = 1, 10
    a = 1
  end do
end subroutine test_sub
"""


def test_no_directives():
    """Test that the FortranReader is without directives by default"""
    reader = FortranReader()
    psyir = reader.psyir_from_source(CODE_WITH_DIRECTIVE, ignore_comments=False)

    loop = psyir.walk(Loop)[0]
    assert loop.preceding_comment == "Comment on loop 'do i = 1, 10'"


def test_directives():
    """Test that the FortranReader is able to read directives"""
    reader = FortranReader()
    psyir = reader.psyir_from_source(CODE_WITH_DIRECTIVE, ignore_comments=False, ignore_directives=False)

    loop = psyir.walk(Loop)[0]
    assert loop.preceding_comment == "Comment on loop 'do i = 1, 10'\n$omp parallel do"


EXPECTED_WITH_DIRECTIVES = """subroutine test_sub()
  integer :: a
  integer :: i

  ! Comment on loop 'do i = 1, 10'
  !$omp parallel do
  do i = 1, 10, 1
    a = 1
  enddo

end subroutine test_sub
"""

@pytest.mark.xfail(reason="Directive is written back as '! $omp parallel do'"
                         "instead of '!$omp parallel do'")
def test_write_directives():
    """Test that the directives are written back to the code"""
    reader = FortranReader()
    writer = FortranWriter()
    psyir = reader.psyir_from_source(CODE_WITH_DIRECTIVE, ignore_comments=False, ignore_directives=False)
    generated_code = writer(psyir)
    assert generated_code == EXPECTED_WITH_DIRECTIVES
