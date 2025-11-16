#!/usr/bin/env python3
"""
RemoteOK Job Scraping Integration

Fetches jobs from RemoteOK API, scores them using SimpleJobScorer,
and stores results in the jobs-tracker database.

Author: Karthik Shetty
Created: 2025-11-14
"""

import requests
import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from pathlib import Path

from simple_scorer import SimpleJobScorer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RemoteOKIntegration:
    """
    Integrate RemoteOK job scraping with SimpleJobScorer.

    Fetches jobs from RemoteOK API, filters by relevance, scores against
    resume profile, and stores high-quality matches in database.
    """

    def __init__(self, db_path: str = "data/jobs-tracker.db"):
        """
        Initialize RemoteOK integration.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.base_url = "https://remoteok.com/api"

        # Initialize scorer
        try:
            self.scorer = SimpleJobScorer(config_path="data/resume_config.json")
            logger.info("SimpleJobScorer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize scorer: {e}")
            raise

        # Verify database path exists
        db_file = Path(db_path)
        if not db_file.parent.exists():
            raise FileNotFoundError(f"Database directory does not exist: {db_file.parent}")

        logger.info(f"RemoteOK integration initialized (DB: {db_path})")

    def fetch_jobs(self, limit: int = 100) -> List[Dict]:
        """
        Fetch jobs from RemoteOK API.

        Args:
            limit: Maximum number of jobs to fetch

        Returns:
            List of job dictionaries
        """
        try:
            logger.info(f"Fetching jobs from {self.base_url}")

            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; JobTracker/1.0)'
            }

            response = requests.get(
                self.base_url,
                headers=headers,
                timeout=15
            )
            response.raise_for_status()

            jobs = response.json()

            # Skip first item if it contains metadata (has 'legal' key)
            if jobs and isinstance(jobs[0], dict) and 'legal' in jobs[0]:
                jobs = jobs[1:]
                logger.debug("Skipped metadata item")

            # Limit results
            jobs = jobs[:limit]

            logger.info(f"Successfully fetched {len(jobs)} jobs from RemoteOK")
            return jobs

        except requests.exceptions.Timeout:
            logger.error("Request timeout while fetching jobs from RemoteOK")
            print("❌ Error: Request timed out. Please check your internet connection.")
            return []

        except requests.exceptions.ConnectionError:
            logger.error("Connection error while fetching jobs from RemoteOK")
            print("❌ Error: Could not connect to RemoteOK API. Please check your internet.")
            return []

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error from RemoteOK API: {e}")
            print(f"❌ Error: RemoteOK API returned error: {e}")
            return []

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            print("❌ Error: Invalid JSON response from RemoteOK API.")
            return []

        except Exception as e:
            logger.error(f"Unexpected error fetching jobs: {e}", exc_info=True)
            print(f"❌ Error: Unexpected error occurred: {e}")
            return []

    def filter_relevant_jobs(self, jobs: List[Dict]) -> List[Dict]:
        """
        Filter jobs by relevance to QA/Data/Testing domains.

        Args:
            jobs: List of all jobs from API

        Returns:
            Filtered list of relevant jobs
        """
        # Keywords to search for (case-insensitive)
        keywords = [
            'qa', 'test', 'quality', 'automation', 'sdet',
            'etl', 'data', 'sql', 'analytics', 'validation',
            'quality assurance', 'test engineer', 'data engineer',
            'backend', 'api testing', 'data quality'
        ]

        relevant_jobs = []

        for job in jobs:
            try:
                # Combine searchable text
                position = job.get('position', '').lower()
                description = job.get('description', '').lower()
                tags = job.get('tags', [])
                tags_text = ' '.join(tags).lower() if tags else ''

                # Combine all text for searching
                searchable_text = f"{position} {description} {tags_text}"

                # Check if any keyword matches
                if any(keyword in searchable_text for keyword in keywords):
                    relevant_jobs.append(job)

            except Exception as e:
                logger.warning(f"Error processing job for filtering: {e}")
                continue

        logger.info(f"Filtered {len(relevant_jobs)} relevant jobs from {len(jobs)} total")
        return relevant_jobs

    def create_scraped_jobs_table(self) -> None:
        """
        Create scraped_jobs table if it doesn't exist.

        Creates table with proper schema and indexes for efficient querying.
        """
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()

            # Create main table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scraped_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    external_id TEXT UNIQUE NOT NULL,
                    source TEXT DEFAULT 'RemoteOK',
                    job_title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    job_url TEXT NOT NULL,
                    location TEXT,
                    description TEXT,
                    tags TEXT,
                    salary_range TEXT,
                    posted_date TEXT,
                    match_score REAL,
                    classification TEXT,
                    matched_skills TEXT,
                    matched_domains TEXT,
                    red_flags TEXT,
                    recommendation TEXT,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    imported_to_opportunities BOOLEAN DEFAULT 0
                )
            """)

            # Create indexes for efficient querying
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_scraped_jobs_score
                ON scraped_jobs(match_score DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_scraped_jobs_classification
                ON scraped_jobs(classification)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_scraped_jobs_date
                ON scraped_jobs(scraped_at DESC)
            """)

            conn.commit()
            logger.info("Created/verified scraped_jobs table and indexes")

        except sqlite3.Error as e:
            logger.error(f"Database error creating table: {e}")
            raise

        finally:
            if conn:
                conn.close()

    def score_and_store_jobs(self, jobs: List[Dict]) -> Tuple[int, int]:
        """
        Score jobs and store in database.

        Args:
            jobs: List of job dictionaries to score and store

        Returns:
            Tuple of (total_stored, high_fit_count)
        """
        # Ensure table exists
        self.create_scraped_jobs_table()

        stored_count = 0
        high_fit_count = 0

        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()

            for idx, job in enumerate(jobs, 1):
                try:
                    # Prepare job data for scoring
                    position = job.get('position', 'Unknown Position')
                    company = job.get('company', 'Unknown Company')
                    description = job.get('description', '')

                    # Handle location (can be array or string)
                    location_raw = job.get('location', 'Remote')
                    if isinstance(location_raw, list):
                        location = ', '.join(location_raw) if location_raw else 'Remote'
                    else:
                        location = location_raw if location_raw else 'Remote'

                    # Handle tags
                    tags_raw = job.get('tags', [])
                    tags = ', '.join(tags_raw) if tags_raw else ''

                    # Prepare job_data for scorer
                    job_data = {
                        'title': position,
                        'description': description,
                        'location': location,
                        'company': company,
                        'tags': tags,
                        'experience_required': ''  # RemoteOK doesn't provide this consistently
                    }

                    # Score the job
                    score_result = self.scorer.score_job(job_data)

                    # Prepare external_id
                    external_id = str(job.get('id', f"remoteok_{idx}"))

                    # Prepare job URL
                    slug = job.get('slug', '')
                    job_url = job.get('url', f"https://remoteok.com/remote-jobs/{slug}")

                    # Prepare salary range
                    salary_min = job.get('salary_min', '')
                    salary_max = job.get('salary_max', '')
                    if salary_min and salary_max:
                        salary_range = f"${salary_min:,} - ${salary_max:,}"
                    elif salary_min:
                        salary_range = f"${salary_min:,}+"
                    else:
                        salary_range = None

                    # Prepare posted date
                    posted_date = job.get('date', datetime.now().isoformat())

                    # Truncate description to 2000 characters
                    description_truncated = description[:2000] if description else ''

                    # Insert into database (IGNORE duplicates)
                    cursor.execute("""
                        INSERT OR IGNORE INTO scraped_jobs (
                            external_id, source, job_title, company, job_url, location,
                            description, tags, salary_range, posted_date,
                            match_score, classification, matched_skills, matched_domains,
                            red_flags, recommendation
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        external_id,
                        'RemoteOK',
                        position,
                        company,
                        job_url,
                        location,
                        description_truncated,
                        tags,
                        salary_range,
                        posted_date,
                        score_result['final_score'],
                        score_result['classification'],
                        json.dumps(score_result['matched_skills']),
                        json.dumps(score_result['matched_domains']),
                        json.dumps(score_result['red_flags']),
                        score_result['recommendation']
                    ))

                    # Check if row was actually inserted (not a duplicate)
                    if cursor.rowcount > 0:
                        stored_count += 1

                        # Track high-fit jobs
                        if score_result['classification'] in ['EXCELLENT', 'HIGH_FIT']:
                            high_fit_count += 1
                            print(f"✅ HIGH FIT ({score_result['final_score']:.0f}%): {company} - {position}")
                        elif score_result['classification'] == 'MEDIUM_FIT':
                            print(f"⚠️  MEDIUM ({score_result['final_score']:.0f}%): {company} - {position}")

                except Exception as e:
                    logger.warning(f"Error processing job '{job.get('position', 'Unknown')}': {e}")
                    print(f"⚠️  Error processing job: {e}")
                    continue

            # Commit all changes
            conn.commit()
            logger.info(f"Stored {stored_count} jobs ({high_fit_count} high-fit)")

        except sqlite3.Error as e:
            logger.error(f"Database error during storage: {e}")
            print(f"❌ Database error: {e}")
            return (0, 0)

        finally:
            if conn:
                conn.close()

        return (stored_count, high_fit_count)

    def get_summary_stats(self) -> Dict:
        """
        Get summary statistics of scraped jobs.

        Returns:
            Dictionary with job statistics
        """
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()

            stats = {}

            # Total jobs
            cursor.execute("SELECT COUNT(*) FROM scraped_jobs")
            stats['total_jobs'] = cursor.fetchone()[0]

            # Excellent (85+)
            cursor.execute("SELECT COUNT(*) FROM scraped_jobs WHERE match_score >= 85")
            stats['excellent'] = cursor.fetchone()[0]

            # High fit (75-84)
            cursor.execute("""
                SELECT COUNT(*) FROM scraped_jobs
                WHERE match_score >= 75 AND match_score < 85
            """)
            stats['high_fit'] = cursor.fetchone()[0]

            # Medium fit (65-74)
            cursor.execute("""
                SELECT COUNT(*) FROM scraped_jobs
                WHERE match_score >= 65 AND match_score < 75
            """)
            stats['medium_fit'] = cursor.fetchone()[0]

            # Low fit (40-64)
            cursor.execute("""
                SELECT COUNT(*) FROM scraped_jobs
                WHERE match_score >= 40 AND match_score < 65
            """)
            stats['low_fit'] = cursor.fetchone()[0]

            # No fit (<40)
            cursor.execute("SELECT COUNT(*) FROM scraped_jobs WHERE match_score < 40")
            stats['no_fit'] = cursor.fetchone()[0]

            # Top 5 jobs
            cursor.execute("""
                SELECT company, job_title, match_score
                FROM scraped_jobs
                ORDER BY match_score DESC
                LIMIT 5
            """)
            stats['top_5'] = cursor.fetchall()

            logger.info("Retrieved summary statistics")
            return stats

        except sqlite3.Error as e:
            logger.error(f"Database error getting stats: {e}")
            return {}

        finally:
            if conn:
                conn.close()

    def run(self, limit: int = 100, show_stats: bool = True) -> Tuple[int, int]:
        """
        Run complete scraping pipeline.

        Args:
            limit: Maximum number of jobs to fetch from API
            show_stats: Whether to display summary statistics

        Returns:
            Tuple of (total_stored, high_fit_count)
        """
        print("\n" + "="*70)
        print("🚀 RemoteOK Job Scraping Pipeline")
        print("="*70)

        # Step 1: Fetch jobs
        print("\n🔍 Step 1/3: Fetching jobs from RemoteOK API...")
        jobs = self.fetch_jobs(limit)

        if not jobs:
            print("❌ No jobs fetched. Exiting.")
            return (0, 0)

        print(f"   ✅ Fetched {len(jobs)} jobs")

        # Step 2: Filter relevant jobs
        print("\n🎯 Step 2/3: Filtering relevant jobs...")
        relevant_jobs = self.filter_relevant_jobs(jobs)

        if not relevant_jobs:
            print("❌ No relevant jobs found after filtering. Exiting.")
            return (0, 0)

        print(f"   ✅ Found {len(relevant_jobs)} relevant jobs "
              f"(filtered by QA/Data/Testing keywords)")

        # Step 3: Score and store
        print(f"\n⚖️  Step 3/3: Scoring and storing jobs in database...")
        print(f"   Database: {self.db_path}\n")

        stored, high_fit = self.score_and_store_jobs(relevant_jobs)

        print(f"\n   ✅ Stored {stored} jobs ({high_fit} high-fit candidates)")

        # Show stats if requested
        if show_stats:
            print("\n" + "="*70)
            print("📊 Scraping Summary")
            print("="*70)

            stats = self.get_summary_stats()

            if stats:
                print(f"\nTotal Jobs Scraped: {stats['total_jobs']}")
                print(f"\n📈 Score Distribution:")
                print(f"   🎯 Excellent (85-100):  {stats['excellent']:3d} jobs")
                print(f"   ✅ High Fit (75-84):    {stats['high_fit']:3d} jobs")
                print(f"   ⚠️  Medium Fit (65-74):  {stats['medium_fit']:3d} jobs")
                print(f"   ❌ Low Fit (40-64):     {stats['low_fit']:3d} jobs")
                print(f"   🚫 No Fit (<40):        {stats['no_fit']:3d} jobs")

                if stats['top_5']:
                    print(f"\n🏆 Top 5 Matches:")
                    for idx, (company, title, score) in enumerate(stats['top_5'], 1):
                        print(f"   {idx}. [{score:.1f}%] {company} - {title}")

                print("\n💡 Next Steps:")
                if high_fit > 0:
                    print(f"   • Review {high_fit} high-fit jobs in dashboard")
                    print(f"   • Import promising candidates to opportunities table")
                else:
                    print(f"   • No high-fit jobs found in this batch")
                    print(f"   • Try scraping more jobs or adjust filters")

                print(f"\n📂 Database Location: {self.db_path}")
                print(f"   View results: sqlite3 {self.db_path} "
                      f"'SELECT * FROM scraped_jobs ORDER BY match_score DESC LIMIT 10;'")

        print("\n" + "="*70)
        print("✅ Scraping pipeline complete!")
        print("="*70 + "\n")

        return (stored, high_fit)


if __name__ == "__main__":
    """Run RemoteOK job scraping pipeline."""

    print("\n" + "🔷"*35)
    print("RemoteOK Job Scraper with AI-Powered Scoring")
    print("🔷"*35)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    try:
        # Initialize integration
        integrator = RemoteOKIntegration(db_path="data/jobs-tracker.db")

        # Run scraping pipeline
        stored, high_fit = integrator.run(limit=100, show_stats=True)

        # Final summary
        print(f"\n🎉 Scraping complete!")
        print(f"   • Total jobs stored: {stored}")
        print(f"   • High-fit candidates: {high_fit}")

        if high_fit > 0:
            print(f"\n✨ Great news! Found {high_fit} jobs worth applying to immediately.")
        else:
            print(f"\n💡 No high-fit jobs in this batch. Try again later or adjust filters.")

        print("\n📋 Quick Commands:")
        print("   # View high-fit jobs")
        print("   sqlite3 data/jobs-tracker.db \"SELECT company, job_title, match_score "
              "FROM scraped_jobs WHERE match_score >= 75 ORDER BY match_score DESC;\"")

        print("\n   # Count by classification")
        print("   sqlite3 data/jobs-tracker.db \"SELECT classification, COUNT(*) "
              "FROM scraped_jobs GROUP BY classification ORDER BY match_score DESC;\"")

        print("\n   # View latest scrape")
        print("   sqlite3 data/jobs-tracker.db \"SELECT * FROM scraped_jobs "
              "ORDER BY scraped_at DESC LIMIT 5;\"")

    except FileNotFoundError as e:
        logger.error(f"Configuration error: {e}")
        print(f"\n❌ Error: {e}")
        print("Please ensure data/resume_config.json and data/jobs-tracker.db exist.")

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n❌ Fatal error: {e}")
        print("Please check logs for details.")

    finally:
        print(f"\nFinished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
