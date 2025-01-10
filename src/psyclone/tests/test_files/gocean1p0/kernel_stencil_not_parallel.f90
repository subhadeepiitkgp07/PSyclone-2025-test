! -----------------------------------------------------------------------------
! BSD 3-Clause License
!
! Copyright (c) 2018-2025, Science and Technology Facilities Council
! All rights reserved.
!
! Redistribution and use in source and binary forms, with or without
! modification, are permitted provided that the following conditions are met:
!
! * Redistributions of source code must retain the above copyright notice, this
!   list of conditions and the following disclaimer.
!
! * Redistributions in binary form must reproduce the above copyright notice,
!   this list of conditions and the following disclaimer in the documentation
!   and/or other materials provided with the distribution.
!
! * Neither the name of the copyright holder nor the names of its
!   contributors may be used to endorse or promote products derived from
!   this software without specific prior written permission.
!
! THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
! AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
! IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
! DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
! FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
! DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
! SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
! CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
! OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
! OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
! -----------------------------------------------------------------------------
! Authors R. W. Ford, A. R. Porter, STFC Daresbury Lab
! Modified: J. Henrichs, Bureau of Meteorology

module kernel_stencil_not_parallel
  use argument_mod
  use field_mod
  use grid_mod
  use kernel_mod
  use kind_params_mod

  implicit none

  private

  public stencil_not_parallel, stencil_not_parallel_code

  type, extends(kernel_type) :: stencil_not_parallel
     type(go_arg), dimension(2) :: meta_args =    &
          ! We deliberately specify an incorrect stencil value
          ! for the first kernel argument in order to test the 
          ! parser: stencil accesses are not permitted on variables
          ! that are written to."

          (/ go_arg(GO_READWRITE, GO_CT, GO_STENCIL(010,010,010)),  & ! u
             go_arg(GO_WRITE,  GO_CT, GO_POINTWISE)   & ! v
           /)
     integer :: ITERATES_OVER = GO_INTERNAL_PTS

     integer :: index_offset = GO_OFFSET_SW

  contains
    procedure, nopass :: code => stencil_not_parallel_code
  end type stencil_not_parallel

contains

  !===================================================

  !> Some dummy operation, that cannot be executed in parallel
  !! due to stencil read and write access
  subroutine stencil_not_parallel_code(i, j, u, v)
    implicit none
    integer,  intent(in) :: i, j
    real(go_wp), intent(inout), dimension(:,:) :: u
    real(go_wp), intent(in),  dimension(:,:) :: v
    real(go_wp) :: tmp

    v(i,j) = u(i, j-1) + u(i,j) + u(i, j+1)
    u(i,j) = u(i,j) / 3
    v(i,j) = v(i,j) + 1

  end subroutine stencil_not_parallel_code

end module kernel_stencil_not_parallel
