# src/ingestion/load_helloao.py
import sqlite3
import pandas as pd
from pathlib import Path
from ..models import BiblicalVerse

class HelloAOLoader:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.conn = None
        
    def connect(self):
        """Connect to HelloAO Bible database"""
        self.conn = sqlite3.connect(self.db_path)
        
    def get_available_greek_translations(self) -> pd.DataFrame:
        """Find all available Greek translations"""
        if self.conn is None:
            self.connect()
        if self.conn is None:
            raise RuntimeError("Failed to establish database connection")
        query = """
        SELECT id, name, shortName, englishName 
        FROM translations 
        WHERE language IN ('grc', 'grk')
        OR englishName LIKE '%Greek%'
        OR name LIKE '%Ἑλληνικά%'
        """
        return pd.read_sql(query, self.conn)
    
    def load_translation(self, translation_id: str) -> List[BiblicalVerse]:
        """Load all verses from a specific translation"""
        verses = []
        
        # Get books for this translation
        books_query = f"""
        SELECT * FROM json_each(
            (SELECT books FROM translations WHERE id = '{translation_id}')
        )
        """
        # Implementation continues...
        
        return verses

# src/ingestion/load_cntr.py
from pathlib import Path
import re

class CNTRLoader:
    """Load Statistical Restoration & BHP texts"""
    
    def __init__(self, sr_path: str, bhp_path: str):
        self.sr_path = Path(sr_path)
        self.bhp_path = Path(bhp_path)
        
    def load_sr_text(self) -> List[BiblicalVerse]:
        """Load Statistical Restoration Greek NT"""
        verses = []
        
        # SR format: BCVWGN (Book/Chapter/Verse/Word/Greek/Num)
        # Parse the text files from SR repo
        
        for text_file in self.sr_path.glob("*.txt"):
            with open(text_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Parse SR format and extract verses
                parsed_verses = self.parse_sr_format(content)
                verses.extend(parsed_verses)
        
        return verses
    
    def parse_sr_format(self, content: str) -> List[BiblicalVerse]:
        """Parse SR's BCVWGN format"""
        # Implementation for parsing
        pass

# src/ingestion/orchestrator.py
class DataIngestionOrchestrator:
    """Coordinate loading from all sources"""
    
    def __init__(self):
        self.helloao_loader = HelloAOLoader("data/raw/bible.db")
        self.cntr_loader = CNTRLoader(
            "data/raw/SR",
            "data/raw/BHP"
        )
        
    async def ingest_all_sources(self):
        """Load and consolidate all biblical texts"""
        print("Loading HelloAO data...")
        helloao_verses = self.helloao_loader.load_translation("GREEK_ID")
        
        print("Loading CNTR Statistical Restoration...")
        sr_verses = self.cntr_loader.load_sr_text()
        
        print("Consolidating and deduplicating...")
        all_verses = self.consolidate(helloao_verses, sr_verses)
        
        print("Saving to processed database...")
        self.save_to_database(all_verses)
        
        return all_verses