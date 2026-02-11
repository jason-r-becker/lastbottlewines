# %%

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from lastbottlewines.utils import data_dir

# %%

class WineDatabase:
    """Database for tracking wines and user scores over time."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the database.
        
        Args:
            db_path: Path to the database file. If None, uses default location.
        """
        if db_path is None:
            db_path = data_dir("wines.db")
        
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
    
    def _create_tables(self):
        """Create the wines and user_scores tables if they don't exist."""
        cursor = self.conn.cursor()
        
        # Wines table: stores wine data at specific timestamps
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL UNIQUE,
                wine_name TEXT NOT NULL,
                price REAL NOT NULL
            )
        """)
        
        # User scores table: stores user ratings for wines at specific timestamps
        # Aligned with wine timestamps so all users score the same wine at the same time
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                wine_id INTEGER NOT NULL,
                wine_name TEXT NOT NULL,
                score INTEGER NOT NULL CHECK(score >= 0 AND score <= 100),
                timestamp DATETIME NOT NULL,
                FOREIGN KEY (wine_id) REFERENCES wines(id),
                UNIQUE(user_id, wine_id, timestamp)
            )
        """)
        
        self.conn.commit()
    
    def add_wine(self, wine_name: str, price: float, timestamp: Optional[datetime] = None) -> int:
        """
        Record a wine at a given timestamp.
        
        Args:
            wine_name: Name of the wine
            price: Price of the wine
            timestamp: When this wine was recorded. If None, uses current time.
        
        Returns:
            The wine_id of the added wine
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO wines (timestamp, wine_name, price)
            VALUES (?, ?, ?)
        """, (timestamp, wine_name, price))
        self.conn.commit()
        
        return cursor.lastrowid
    
    def add_user_score(self, user_id: str, wine_id: int, score: int, timestamp: Optional[datetime] = None) -> int:
        """
        Record a user's score for a wine at a specific timestamp.
        
        Args:
            user_id: Unique identifier for the user
            wine_id: ID of the wine being scored
            score: Score from 0-100
            timestamp: When the score was given. If None, uses current time.
        
        Returns:
            The score record id
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        if not (0 <= score <= 100):
            raise ValueError(f"Score must be between 0 and 100, got {score}")
        
        # Fetch the wine name from the wine_id
        wine = self.get_wine(wine_id)
        if not wine:
            raise ValueError(f"Wine with id {wine_id} not found")
        wine_name = wine['wine_name']
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO user_scores (user_id, wine_id, wine_name, score, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, wine_id, wine_name, score, timestamp))
        self.conn.commit()
        
        return cursor.lastrowid
    
    def get_wine(self, wine_id: int) -> Optional[dict]:
        """Get a wine by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM wines WHERE id = ?", (wine_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_latest_wine(self) -> Optional[dict]:
        """Get the most recently recorded wine."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM wines ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def is_duplicate_wine(self, wine_name: str, days: int = 7) -> bool:
        """Check if wine_name appears in the last N days of history."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM wines WHERE wine_name = ? "
            f"AND timestamp >= datetime('now', '-{days} days')",
            (wine_name,),
        )
        return cursor.fetchone() is not None
    
    def get_wines_by_date_range(self, start_date: datetime, end_date: datetime) -> List[dict]:
        """Get all wines recorded within a date range."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM wines 
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp DESC
        """, (start_date, end_date))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_user_scores_for_wine(self, wine_id: int) -> List[dict]:
        """Get all user scores for a specific wine."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM user_scores 
            WHERE wine_id = ?
            ORDER BY timestamp DESC
        """, (wine_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_user_score(self, user_id: str, wine_id: int) -> Optional[dict]:
        """Get a specific user's score for a wine."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM user_scores 
            WHERE user_id = ? AND wine_id = ?
        """, (user_id, wine_id))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_user_scores(self, user_id: str) -> List[dict]:
        """Get all scores for a specific user."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM user_scores 
            WHERE user_id = ?
            ORDER BY timestamp DESC
        """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_average_score_for_wine(self, wine_id: int) -> Optional[float]:
        """Get the average score for a wine across all users."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT AVG(score) as avg_score FROM user_scores 
            WHERE wine_id = ?
        """, (wine_id,))
        row = cursor.fetchone()
        return row['avg_score'] if row and row['avg_score'] is not None else None
    
    def get_scores_at_timestamp(self, timestamp: datetime) -> List[dict]:
        """Get all user scores recorded at a specific timestamp."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM user_scores 
            WHERE timestamp = ?
            ORDER BY user_id
        """, (timestamp,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_wine_and_scores_at_timestamp(self, timestamp: datetime) -> Optional[dict]:
        """Get the wine and all user scores at a specific timestamp."""
        wine = None
        cursor = self.conn.cursor()
        
        # Get wine
        cursor.execute("SELECT * FROM wines WHERE timestamp = ?", (timestamp,))
        wine_row = cursor.fetchone()
        wine = dict(wine_row) if wine_row else None
        
        if not wine:
            return None
        
        # Get scores for this wine
        scores = self.get_scores_at_timestamp(timestamp)
        
        return {
            'wine': wine,
            'scores': scores
        }
    
    def close(self):
        """Close the database connection."""
        self.conn.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
