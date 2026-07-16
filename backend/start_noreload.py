import warnings
import os

os.environ['NPY_DISABLE_LAPACK'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'

warnings.filterwarnings('ignore', category=RuntimeWarning)
warnings.filterwarnings('ignore', category=UserWarning)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
