import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from pavement_intelligence.database.connection import Base, engine
Base.metadata.create_all(engine)
print("Base de datos inicializada")
