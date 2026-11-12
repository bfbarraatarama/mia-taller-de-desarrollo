"""Tarea 3.3: selección del dispositivo con torch.cuda.is_available simulado."""

import pytest

from dispositivo import elegir_dispositivo
from errores import DiarizacionError


def test_auto_sin_gpu_usa_cpu(torch_falso):
    torch_falso(cuda=False)
    assert elegir_dispositivo("auto") == "cpu"


def test_auto_con_gpu_usa_cuda(torch_falso):
    torch_falso(cuda=True)
    assert elegir_dispositivo("auto") == "cuda"


def test_cpu_forzada_con_gpu_disponible(torch_falso):
    torch_falso(cuda=True)
    assert elegir_dispositivo("cpu") == "cpu"


def test_cuda_pedida_sin_gpu_es_error(torch_falso):
    torch_falso(cuda=False)
    with pytest.raises(DiarizacionError) as e:
        elegir_dispositivo("cuda")
    assert e.value.etapa == "dispositivo"
    assert "no hay CUDA disponible" in e.value.mensaje and "--device cpu" in e.value.mensaje


def test_cuda_pedida_con_gpu(torch_falso):
    torch_falso(cuda=True)
    assert elegir_dispositivo("cuda") == "cuda"


def test_modo_desconocido():
    with pytest.raises(DiarizacionError) as e:
        elegir_dispositivo("tpu")
    assert e.value.etapa == "parametros"
