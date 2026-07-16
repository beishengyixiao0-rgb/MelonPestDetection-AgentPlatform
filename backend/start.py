import warnings
import os

os.environ['NPY_DISABLE_LAPACK'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'

warnings.filterwarnings('ignore', category=RuntimeWarning)
warnings.filterwarnings('ignore', category=UserWarning)

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    from uvicorn.main import main
    sys.exit(main())
