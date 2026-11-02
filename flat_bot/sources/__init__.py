from .avito import Avito
from .cian import Cian
from .domclick import Domclick
from .etagi import Etagi
from .n1 import N1
from .yandex import Yandex

REGISTRY = {cls.name: cls for cls in (Cian, Avito, Domclick, Yandex, Etagi, N1)}
