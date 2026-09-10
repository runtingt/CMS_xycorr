#!/usr/bin/env bash
# Non-interactive analysis environment shared by local and HTCondor jobs.

_xycorr_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_xycorr_lcg=/cvmfs/sft.cern.ch/lcg/views/LCG_107/x86_64-el9-gcc13-opt/setup.sh
export XDG_CACHE_HOME="${_xycorr_root}/.workflow/cache"
mkdir -p "${XDG_CACHE_HOME}"

if [[ ! -f "${_xycorr_lcg}" ]]; then
    echo "LCG view not found: ${_xycorr_lcg}" >&2
    return 1 2>/dev/null || exit 1
fi

unset PYTHONHOME
_xycorr_restore_nounset=false
if [[ $- == *u* ]]; then
    _xycorr_restore_nounset=true
    set +u
fi
source "${_xycorr_lcg}"
if [[ "${_xycorr_restore_nounset}" == true ]]; then
    set -u
fi

if [[ -f "${_xycorr_root}/.venv-workflow/bin/activate" ]]; then
    source "${_xycorr_root}/.venv-workflow/bin/activate"
fi

unset _xycorr_root _xycorr_lcg _xycorr_restore_nounset
