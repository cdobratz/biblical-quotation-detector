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