import sys
from pathlib import Path

# Make `import app` and `import tests.fake_gnani` work no matter where pytest is started from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
