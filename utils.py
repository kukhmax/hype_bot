
import math

def round_step_size(quantity: float, step_size: float) -> float:
    """
    Округляет число до ближайшего шага (step size).
    Нужно для корректной отправки объемов на биржу.
    """
    if step_size < 0:
        return quantity
    return float(int(quantity / step_size) * step_size)

def get_precision(step_size: float) -> int:
    """Определяет количество знаков после запятой по шагу цены."""
    if step_size == 0:
        return 0
    return int(round(-math.log(step_size, 10), 0))
