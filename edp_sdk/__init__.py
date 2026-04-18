from .pathing import *
from .semantics import *
from .contextualizer import *
from .savoir import *
from .analytics import *
from .operational import *
from .core import *
from .protocol import *
from .persistence import *
from .intelligence import *
from .policy import *
from .canonical import *

from .envlang import *

from .maintenance import *

from .release import *

from .store_adapters import *

__version__ = "2.0.0"

ensure_portable_tmp()

from .store_adapters import VectorStoreAdapter, GraphStoreAdapter, TensorStoreAdapter, DatasetStoreAdapter, StoreProjectionSuite
