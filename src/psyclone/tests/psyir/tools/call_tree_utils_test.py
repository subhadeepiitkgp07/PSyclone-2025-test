# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2020-2023, Science and Technology Facilities Council.
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
# Author: A. R. Porter, STFC Daresbury Lab
# Modified: S. Siso, STFC Daresbury Lab
# Modified: J. Henrichs, Bureau of Meteorology
# -----------------------------------------------------------------------------

''' This module contains the pytest tests for the Routine class. '''

import os
import pytest

from psyclone.core import Signature
from psyclone.domain.lfric import LFRicKern
from psyclone.parse import ModuleManager
from psyclone.psyGen import BuiltIn
from psyclone.psyir.nodes import (Reference, Schedule)
from psyclone.psyir.tools import CallTreeUtils, ReadWriteInfo
from psyclone.tests.utilities import get_base_path, get_invoke
from psyclone.tests.parse.conftest import mod_man_test_setup_directories


# -----------------------------------------------------------------------------
@pytest.mark.usefixtures("clear_module_manager_instance")
def test_call_tree_compute_all_non_locals_non_kernel():
    '''Test _compute_all_non_locals() functionality for source code
    that has no kernels.
    '''
    test_dir = os.path.join(get_base_path("dynamo0.3"), "driver_creation")
    mod_man = ModuleManager.get()
    mod_man.add_search_path(test_dir)
    mod_info = mod_man.get_module_info("module_call_tree_mod")

    ctu = CallTreeUtils()

    # Check that using a local variable is not reported:
    psyir = mod_info.get_psyir("local_var_sub")
    info = ctu._compute_all_non_locals(psyir)
    assert info == []

    # Check using a variable that is used from the current module
    psyir = mod_info.get_psyir("module_var_sub")
    info = ctu._compute_all_non_locals(psyir)
    assert info == [('reference', 'module_call_tree_mod',
                     Signature("module_var"))]

    # Test that a call of a function in the same module is reported as
    # module routine:
    psyir = mod_info.get_psyir("call_local_function")
    info = ctu._compute_all_non_locals(psyir)
    assert info == [('routine', 'module_call_tree_mod',
                     Signature("module_function"))]

    # Check using a local constant
    psyir = mod_info.get_psyir("local_const_sub")
    info = ctu._compute_all_non_locals(psyir)
    assert info == []

    # Check using an argument
    psyir = mod_info.get_psyir("argument_sub")
    info = ctu._compute_all_non_locals(psyir)
    assert info == []

    # Check assigning the result to a function
    psyir = mod_info.get_psyir("module_function")
    info = ctu._compute_all_non_locals(psyir)
    assert info == []

    # Check calling an undeclared function
    psyir = mod_info.get_psyir("calling_unknown_subroutine")
    info = ctu._compute_all_non_locals(psyir)
    assert info == [("routine", None, Signature("unknown_subroutine"))]

    # Check calling an imported subroutine
    psyir = mod_info.get_psyir("calling_imported_subroutine")
    info = ctu._compute_all_non_locals(psyir)
    assert info == [("routine", "some_module", Signature("module_subroutine"))]

    # Check using an imported symbol
    psyir = mod_info.get_psyir("use_imported_symbol")
    info = ctu._compute_all_non_locals(psyir)
    assert info == [("unknown", "some_module1", Signature("module_var1")),
                    ("unknown", "some_module2", Signature("module_var2"))]

    # Check calling an undeclared function
    psyir = mod_info.get_psyir("intrinsic_call")
    info = ctu._compute_all_non_locals(psyir)
    assert info == []


# -----------------------------------------------------------------------------
@pytest.mark.usefixtures("clear_module_manager_instance")
def test_call_tree_compute_all_non_locals_kernel():
    '''This tests the handling of (LFRic-specific) kernels and builtins. This
    example contains an explicit kernel and a builtin, so both will be tested.

    '''
    # We need to get the PSyIR after being processed by PSyclone, so that the
    # invoke-call and builtin has been replaced with the builtin/kernel
    # objects.
    test_file = os.path.join("driver_creation", "module_with_builtin_mod.f90")
    mod_psyir, _ = get_invoke(test_file, "dynamo0.3", 0, dist_mem=False)
    psyir = mod_psyir.invokes.invoke_list[0].schedule

    # This will return three schedule - the DynInvokeSchedule, and two
    # schedules for the kernel and builtin. Just make sure we have
    # the right parts before doing the actual test:
    schedules = psyir.walk(Schedule)
    assert isinstance(schedules[1].children[0], LFRicKern)
    assert isinstance(schedules[2].children[0], BuiltIn)

    ctu = CallTreeUtils()
    non_locals = ctu._compute_all_non_locals(psyir)

    # There should be exactly one entry - the kernel, but not the builtin:
    assert len(non_locals) == 1
    assert non_locals[0] == ("routine", "testkern_import_symbols_mod",
                             Signature("testkern_import_symbols_code"))


# -----------------------------------------------------------------------------
@pytest.mark.usefixtures("clear_module_manager_instance")
def test_call_tree_get_used_symbols_from_modules():
    '''Tests that we get the used symbols from a routine reported correctly.
    '''
    test_dir = os.path.join(get_base_path("dynamo0.3"), "driver_creation")

    mod_man = ModuleManager.get()
    mod_man.add_search_path(test_dir)

    mod_info = mod_man.get_module_info("testkern_import_symbols_mod")
    psyir = mod_info.get_psyir("testkern_import_symbols_code")
    ctu = CallTreeUtils()
    non_locals = ctu.get_non_local_symbols(psyir)

    non_locals_without_access = set((i[0], i[1], str(i[2]))
                                    for i in non_locals)
    # Check that the expected symbols, modules and internal type are correct:
    expected = set([
            ("unknown", "constants_mod", "eps"),
            ("reference", "testkern_import_symbols_mod",
             "dummy_module_variable"),
            ('routine', 'testkern_import_symbols_mod', "local_func"),
            ("routine", "module_with_var_mod", "module_subroutine"),
            ("unknown", "module_with_var_mod", "module_var_a"),
            ("routine", "testkern_import_symbols_mod", "local_subroutine"),
            ("routine", None, "unknown_subroutine")]
            )
    assert non_locals_without_access == expected

    # Check the handling of a symbol that is not found: _compute_non_locals
    # should return None:
    ref = psyir.walk(Reference)[0]
    # Change the name of the symbol so that it is not in the symbol table:
    ref.symbol._name = "not-in-any-symbol-table"
    psyir = mod_info.get_psyir("testkern_import_symbols_code")
    info = ctu._compute_all_non_locals(psyir)
    print("INFO", info)


# -----------------------------------------------------------------------------
@pytest.mark.usefixtures("clear_module_manager_instance")
def test_call_tree_get_used_symbols_from_modules_renamed():
    '''Tests that we get the used symbols from a routine reported correctly
    when a symbol is renamed, we need to get the original name.
    '''
    test_dir = os.path.join(get_base_path("dynamo0.3"), "driver_creation")

    mod_man = ModuleManager.get()
    mod_man.add_search_path(test_dir)

    mod_info = mod_man.get_module_info("module_renaming_external_var_mod")
    psyir = mod_info.get_psyir("renaming_subroutine")
    ctu = CallTreeUtils()
    non_locals = ctu.get_non_local_symbols(psyir)

    # This example should report just one non-local module:
    # use module_with_var_mod, only: renamed_var => module_var_a
    # It must report the name in the module "module_var_a", not "renamed_var"
    assert len(non_locals) == 1
    # Ignore the last element, variable access
    assert non_locals[0][0:3] == ("unknown", "module_with_var_mod",
                                  Signature("module_var_a"))


# -----------------------------------------------------------------------------
@pytest.mark.usefixtures("clear_module_manager_instance")
def test_call_trees_non_locals_invokes():
    '''Tests that kernels and builtins are handled correctly. We need to get
    the PSyIR after being processed by PSyclone, so that the invoke-call has
    been replaced with the builtin/kernel.
    '''

    # Get the PSyclone-processed PSyIR
    test_file = os.path.join("driver_creation", "module_with_builtin_mod.f90")
    mod_psyir, _ = get_invoke(test_file, "dynamo0.3", 0, dist_mem=False)

    # Now create the module and routine info
    test_dir = os.path.join(get_base_path("dynamo0.3"), "driver_creation")
    mod_man = ModuleManager.get()
    mod_man.add_search_path(test_dir)
    mod_info = mod_man.get_module_info("module_with_builtin_mod")

    # Replace the generic PSyir with the PSyclone processed PSyIR, which
    # has a builtin
    psyir = mod_psyir.invokes.invoke_list[0].schedule

    # This will return three schedule - the DynInvokeSchedule, and two
    # schedules for the kernel and builtin:
    schedules = psyir.walk(Schedule)
    assert isinstance(schedules[1].children[0], LFRicKern)
    assert isinstance(schedules[2].children[0], BuiltIn)

    ctu = CallTreeUtils()
    non_locals = ctu._compute_all_non_locals(psyir)
    # There should be exactly one entry - the kernel, but not the builtin:
    assert len(non_locals) == 1
    assert non_locals[0] == ("routine", "testkern_import_symbols_mod",
                             Signature("testkern_import_symbols_code"))

    # Test that the assignment of the result of a function is not reported
    # as an access:
    mod_info = mod_man.get_module_info("testkern_import_symbols_mod")
    non_locals = ctu._compute_all_non_locals(mod_info.get_psyir("local_func"))
    assert len(non_locals) == 0


# -----------------------------------------------------------------------------
@pytest.mark.usefixtures("clear_module_manager_instance")
def test_dep_tools_resolve_calls_and_unknowns(capsys):
    '''Tests resolving symbols in case of missing modules, subroutines, and
    unknown type (e.g. function call or array access).
    '''
    # Add the search path of the driver creation tests to the
    # module manager:
    test_dir = os.path.join(get_base_path("dynamo0.3"), "driver_creation")
    mod_man = ModuleManager.get()
    mod_man.add_search_path(test_dir)

    # Test if the internal todo handling cannot find a subroutine in the
    # module it is supposed to be in. Create a todo list indicating that
    # the "unknown_subroutine" is in "unknown_module", but this module
    # does not exist:
    todo = [("routine", "unknown_module", Signature("unknown_subroutine"),
             None)]
    ctu = CallTreeUtils()
    rw_info = ReadWriteInfo()
    ctu._resolve_calls_and_unknowns(todo, rw_info)
    out, _ = capsys.readouterr()
    assert "Cannot find module 'unknown_module' - ignored." in out
    assert rw_info.read_list == []
    assert rw_info.write_list == []

    # Now try to find a routine that does not exist in an existing module:
    todo = [('routine', 'module_with_var_mod', Signature("does-not-exist"),
             None)]
    ctu._resolve_calls_and_unknowns(todo, rw_info)
    out, _ = capsys.readouterr()
    assert ("Cannot find symbol 'does-not-exist' in module "
            "'module_with_var_mod' - ignored." in out)
    assert rw_info.read_list == []
    assert rw_info.write_list == []

    # Now ask for an unknown symbol (in this case a subroutine), it
    # should be detected to be a subroutine, and the accesses inside
    # this subroutine should then be reported:
    todo = [('unknown', 'module_with_var_mod',
             Signature("module_subroutine"), None)]
    ctu._resolve_calls_and_unknowns(todo, rw_info)
    assert rw_info.read_list == [('module_with_var_mod',
                                  Signature("module_var_b"))]
    assert rw_info.write_list == [('module_with_var_mod',
                                   Signature("module_var_b"))]


# -----------------------------------------------------------------------------
@pytest.mark.usefixtures("change_into_tmpdir", "clear_module_manager_instance",
                         "mod_man_test_setup_directories")
def test_module_info_generic_interfaces():
    '''Tests the handling of generic interfaces, which should return the
    combined results from all individual subroutines. The example in g_mod
    declares myfunc to be myfunc1 and myfunc2, which are implemented as:
        subroutine myfunc1() ...
            a = p + module_var_1 + module_var
        end subroutine myfunc1

        subroutine myfunc2() ...
            module_var = p + module_var_2
        end subroutine myfunc2
    So they both use the module variable module_var, but myfunc1 reads it,
    myfunc2 writes it. '''
    mod_man = ModuleManager.get()
    mod_man.add_search_path("d2")
    mod_info = mod_man.get_module_info("g_mod")
    ctu = CallTreeUtils()
    # ctu.get_non_local_symbols(mod_info.get_psyir("myfunc"))

    all_routines = mod_info.resolve_routine("myfunc")
    all_non_locals = []
    for routine_name in all_routines:
        all_non_locals.extend(
            ctu.get_non_local_symbols(mod_info.get_psyir(routine_name)))
    # Both functions of the generic interface use 'module_var',
    # and in addition my_func1 uses module_var_1, myfunc2 uses module_var_2
    # So three variables should be reported, i.e. module_var should only
    # be reported once (even though it is used in both functions), and
    # each variable specific to the two functions:
    expected = set([("reference", "g_mod", Signature("module_var_1"),
                     'module_var_1:READ(0)'),
                    ("reference", "g_mod", Signature("module_var_2"),
                     'module_var_2:READ(0)'),
                    ("reference", "g_mod", Signature("module_var"),
                     'module_var:READ(0)'),
                    ("reference", "g_mod", Signature("module_var"),
                     'module_var:WRITE(0)')])
    # Convert the access info to a string for easy comparison:
    assert (set((i[0], i[1], i[2], str(i[3])) for i in all_non_locals) ==
            expected)
