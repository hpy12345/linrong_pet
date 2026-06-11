from __future__ import annotations

import uuid

from linrong_pet.single_instance import SingleInstance


def test_second_instance_requests_activation(qtbot):
    name = f"LinRongPet.Test.{uuid.uuid4()}"
    primary = SingleInstance(name)
    secondary = SingleInstance(name)
    activations = []
    primary.activate_requested.connect(lambda: activations.append(True))

    assert primary.claim()
    assert not secondary.claim()
    qtbot.waitUntil(lambda: activations == [True], timeout=2000)

