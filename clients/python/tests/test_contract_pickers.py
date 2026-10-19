"""The contract pickers of the live runners order only on a contract in
continuous trading.

A contract listing carries contracts whose trading phase is not "CONT":
closed ones, and the contracts the exchange has created but not yet opened,
listed with phase "CLSD" and no ``trading_phase_start``. An order on any of
them is refused, so `verify.py`
and the integration suite's helpers must never pick one to order on.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from voltnir_sdk import ContractState, VoltnirError
from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb2

_SDK = Path(__file__).resolve().parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


verify = _load("verify_under_test", _SDK / "verify.py")
common = _load("integration_common_under_test", _SDK / "tests" / "integration" / "_common.py")

_SOON = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
_TOMORROW = (datetime.now(timezone.utc) + timedelta(hours=20)).isoformat()


def _contract(cid: str, state, phase: str, start: str = _SOON) -> pb2.Contract:
    return pb2.Contract(
        contract_id=cid, state=state, trading_phase=phase, predefined=True, dlvry_start=start
    )


def _not_open_yet(cid: str) -> pb2.Contract:
    # As the gateway lists it on gRPC: its exchange state has no value in the
    # enum, so it reads as unspecified.
    return _contract(cid, ContractState.CONTRACT_STATE_UNSPECIFIED, "CLSD", _TOMORROW)


class _Client:
    def __init__(self, contracts):
        self._contracts = contracts

    def list_contracts(self, area_id):
        return SimpleNamespace(contracts=self._contracts)

    def get_contract(self, area_id, contract_id):
        for c in self._contracts:
            if c.contract_id == contract_id:
                return SimpleNamespace(contract=c)
        raise VoltnirError("not found")


def test_verify_picks_the_contract_in_continuous_trading():
    listed = [_not_open_yet("1"), _contract("2", ContractState.ACTI, "CLSD"), _contract("3", ContractState.ACTI, "CONT")]
    assert verify._find_active_contract(_Client(listed), "A", listed) == "3"


def test_verify_picks_nothing_when_no_contract_is_in_continuous_trading():
    listed = [_not_open_yet("1"), _contract("2", ContractState.ACTI, "CLSD"), _contract("3", ContractState.ACTI, "")]
    assert verify._find_active_contract(_Client(listed), "A", listed) == ""


def test_the_integration_candidates_skip_every_contract_not_in_continuous_trading():
    listed = [_contract("2", ContractState.ACTI, "CLSD"), _not_open_yet("1"), _contract("3", ContractState.ACTI, "CONT")]
    picked = [c.contract_id for c in common._orderable_candidates(_Client(listed), "A")]
    assert picked == ["3"]
